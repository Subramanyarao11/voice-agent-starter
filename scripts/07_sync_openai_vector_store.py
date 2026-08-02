"""Sync the complete extracted corpus into an OpenAI-hosted Vector Store.

This uses the existing ``data/structured/raw_text.jsonl`` output. It does not
download PDFs or run the paid structuring pass again. Exact-text duplicates are
collapsed before upload, UTF-8 text is uploaded with source metadata, and a
local manifest makes reruns resumable by source content hash.

Usage:
    uv run python scripts/07_sync_openai_vector_store.py --dry-run
    uv run python scripts/07_sync_openai_vector_store.py

The created vector-store ID is written to ``data/rag/vector-store-manifest.json``
and should be copied into ``OPENAI_VECTOR_STORE_ID`` in deployment secrets.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from openai import AsyncOpenAI
from openai.types.static_file_chunking_strategy_object_param import (
    StaticFileChunkingStrategyObjectParam,
)
from openai.types.vector_stores.file_batch_create_params import File

from sahaayak_common import (
    REPO_ROOT,
    BudgetError,
    BudgetReservation,
    OpenAIBudgetLedger,
    settings,
)

INPUT_PATH = REPO_ROOT / "data" / "structured" / "raw_text.jsonl"
UPLOAD_DIR = REPO_ROOT / "data" / "rag" / "source_text"
DATASET_NAME = "shrijayan/gov_myscheme"
VECTOR_STORE_NAME = "sahaayak-gov-myscheme"
BATCH_SIZE = 250
UPLOAD_CONCURRENCY = 4
CHUNKING_STRATEGY: StaticFileChunkingStrategyObjectParam = {
    "type": "static",
    "static": {
        "max_chunk_size_tokens": 1200,
        "chunk_overlap_tokens": 200,
    },
}


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    filename: str
    raw_text: str
    source_hash: str
    source_url: str


def canonical_source_id(record_id: str) -> str:
    canonical = re.sub(r"\s+copy$", "", record_id, flags=re.IGNORECASE)
    return re.sub(r"\s*\(\d+\)$", "", canonical)


def canonical_score(record: dict) -> tuple[int, int, int, str]:
    filename = record.get("filename", "")
    stem = Path(filename).stem
    lower = stem.casefold()
    return (
        int(bool(re.search(r"\s+copy$", lower))),
        int(bool(re.search(r"\(\d+\)$", lower))),
        len(stem),
        lower,
    )


def source_url(source_id: str) -> str:
    return f"https://www.myscheme.gov.in/schemes/{quote(source_id, safe='')}"


def load_unique_sources(limit: int | None = None) -> list[SourceRecord]:
    if not INPUT_PATH.exists():
        raise SystemExit(f"{INPUT_PATH} not found — run step 01 first.")

    grouped: dict[str, list[dict]] = {}
    with INPUT_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            normalized = " ".join(record.get("raw_text", "").split())
            if not normalized:
                continue
            fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            grouped.setdefault(fingerprint, []).append(record)

    selected: list[SourceRecord] = []
    for fingerprint, records in grouped.items():
        record = min(records, key=canonical_score)
        record_id = canonical_source_id(str(record.get("id", "")))
        raw_text = str(record.get("raw_text", ""))
        content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        selected.append(
            SourceRecord(
                source_id=record_id,
                filename=str(record.get("filename") or f"{record_id}.pdf"),
                raw_text=raw_text,
                source_hash=content_hash or fingerprint,
                source_url=source_url(record_id),
            )
        )

    selected.sort(key=lambda item: (item.source_id.casefold(), item.source_hash))
    return selected[:limit] if limit else selected


def read_manifest() -> dict:
    path = settings.resolved_openai_rag_manifest_path
    if not path.exists():
        return {"version": 1, "records": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot safely read RAG manifest at {path}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise SystemExit(f"Unsupported RAG manifest at {path}")
    if not isinstance(payload.get("records"), dict):
        raise SystemExit(f"Invalid records in RAG manifest at {path}")
    return payload


def write_manifest(manifest: dict) -> None:
    path = settings.resolved_openai_rag_manifest_path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def render_source(record: SourceRecord) -> str:
    return (
        f"Source ID: {record.source_id}\n"
        f"Source filename: {record.filename}\n"
        f"Source URL: {record.source_url}\n"
        "Verification status: raw machine extraction; not human verified.\n\n"
        f"{record.raw_text}"
    )


def upload_path(record: SourceRecord) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", record.source_id).strip("-")[:80]
    return UPLOAD_DIR / f"{safe_id or 'source'}-{record.source_hash[:16]}.txt"


def attributes_for(record: SourceRecord) -> dict[str, str]:
    return {
        "dataset": DATASET_NAME,
        "source_id": record.source_id,
        "source_hash": record.source_hash,
        "source_url": record.source_url,
        "verification": "raw_extracted",
    }


def prepare_source_file(record: SourceRecord) -> Path:
    path = upload_path(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(render_source(record), encoding="utf-8")
    return path


def manifest_record(manifest: dict, source: SourceRecord) -> dict:
    return manifest["records"].get(source.source_hash, {})


async def ensure_vector_store(
    client: AsyncOpenAI, manifest: dict, source_count: int
) -> str:
    configured_id = settings.openai_vector_store_id.strip()
    manifest_id = str(manifest.get("vector_store_id") or "")
    vector_store_id = configured_id or manifest_id

    if vector_store_id:
        await client.vector_stores.retrieve(vector_store_id=vector_store_id)
        if manifest_id and manifest_id != vector_store_id:
            # File IDs belong to a specific remote store and cannot be reused.
            manifest["records"] = {}
        manifest["vector_store_id"] = vector_store_id
        write_manifest(manifest)
        return vector_store_id

    vector_store = await client.vector_stores.create(
        name=VECTOR_STORE_NAME,
        metadata={
            "dataset": DATASET_NAME,
            "source_count": str(source_count),
            "created_by": "sahaayak-rag-sync",
        },
    )
    manifest["vector_store_id"] = vector_store.id
    manifest["records"] = {}
    write_manifest(manifest)
    print(f"Created OpenAI Vector Store: {vector_store.id}")
    print("Persist this ID as OPENAI_VECTOR_STORE_ID in deployment secrets.")
    return vector_store.id


async def upload_one(
    client: AsyncOpenAI,
    source: SourceRecord,
    semaphore: asyncio.Semaphore,
    budget: OpenAIBudgetLedger,
) -> tuple[SourceRecord, str]:
    async with semaphore:
        path = prepare_source_file(source)
        reservation: BudgetReservation | None = None
        try:
            reservation = budget.reserve_fixed(
                model="openai-vector-store-upload",
                cost_usd=settings.openai_rag_upload_reservation_usd,
                operation=f"rag:upload:{source.source_hash[:16]}",
            )
            with path.open("rb") as handle:
                uploaded = await client.files.create(file=handle, purpose="assistants")
            budget.record_completion(reservation)
            return source, uploaded.id
        except BudgetError:
            raise
        except Exception as exc:
            if reservation is not None:
                budget.record_failure(reservation, exc)
            raise RuntimeError(f"upload failed for {source.source_id}: {exc}") from exc


async def attach_batch(
    client: AsyncOpenAI,
    vector_store_id: str,
    sources: list[SourceRecord],
    manifest: dict,
    budget: OpenAIBudgetLedger,
) -> None:
    if not sources:
        return
    reservation: BudgetReservation | None = None
    try:
        reservation = budget.reserve_fixed(
            model="openai-vector-store-batch",
            cost_usd=settings.openai_rag_batch_reservation_usd,
            operation=f"rag:batch:{sources[0].source_hash[:16]}",
        )
        batch_files: list[File] = [
            {
                "file_id": manifest["records"][source.source_hash]["file_id"],
                "attributes": attributes_for(source),
                "chunking_strategy": CHUNKING_STRATEGY,
            }
            for source in sources
        ]
        batch = await client.vector_stores.file_batches.create_and_poll(
            vector_store_id=vector_store_id,
            files=batch_files,
        )
        budget.record_completion(reservation)
        for source in sources:
            entry = manifest["records"][source.source_hash]
            entry["status"] = "indexed"
            entry["batch_id"] = batch.id
            entry["indexed_at"] = datetime.now(UTC).isoformat()
        write_manifest(manifest)
        print(f"  Indexed batch {batch.id}: {len(sources)} documents", flush=True)
    except BudgetError:
        raise
    except Exception as exc:
        if reservation is not None:
            budget.record_failure(reservation, exc)
        raise RuntimeError(f"vector-store batch failed: {exc}") from exc


async def sync(limit: int | None, concurrency: int, batch_size: int) -> None:
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is not set — this step needs OpenAI.")

    sources = load_unique_sources(limit)
    estimated_bytes = sum(len(render_source(source).encode("utf-8")) for source in sources)
    if estimated_bytes > settings.openai_rag_max_source_bytes:
        raise SystemExit(
            f"Source payload is {estimated_bytes:,} bytes, above the configured RAG "
            f"limit of {settings.openai_rag_max_source_bytes:,} bytes."
        )

    manifest = read_manifest()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    budget = OpenAIBudgetLedger(
        settings.openai_budget_usd,
        settings.resolved_openai_budget_ledger_path,
    )

    try:
        vector_store_id = await ensure_vector_store(client, manifest, len(sources))
        pending_uploads = [
            source
            for source in sources
            if manifest_record(manifest, source).get("status") not in {"uploaded", "indexed"}
        ]
        already_indexed = len(sources) - len(pending_uploads)
        print(
            f"Syncing {len(sources)} unique documents into {vector_store_id}; "
            f"{already_indexed} already present, {len(pending_uploads)} to upload."
        )

        semaphore = asyncio.Semaphore(concurrency)
        failures: list[str] = []
        tasks = [upload_one(client, source, semaphore, budget) for source in pending_uploads]
        for task in asyncio.as_completed(tasks):
            try:
                source, file_id = await task
            except BudgetError:
                raise
            except Exception as exc:
                failures.append(str(exc))
                print(f"  [UPLOAD FAIL] {exc}", flush=True)
                continue
            manifest["records"][source.source_hash] = {
                "source_id": source.source_id,
                "filename": source.filename,
                "source_hash": source.source_hash,
                "file_id": file_id,
                "status": "uploaded",
                "uploaded_at": datetime.now(UTC).isoformat(),
            }
            write_manifest(manifest)
            print(f"  Uploaded {source.source_id}", flush=True)

        if failures:
            raise SystemExit(
                f"{len(failures)} uploads failed; rerun to resume from the manifest."
            )

        pending_index = [
            source
            for source in sources
            if manifest_record(manifest, source).get("status") == "uploaded"
        ]
        for start in range(0, len(pending_index), batch_size):
            await attach_batch(
                client,
                vector_store_id,
                pending_index[start : start + batch_size],
                manifest,
                budget,
            )

        manifest["dataset"] = DATASET_NAME
        manifest["source_count"] = len(sources)
        manifest["estimated_source_bytes"] = estimated_bytes
        manifest["last_sync_at"] = datetime.now(UTC).isoformat()
        write_manifest(manifest)
        print("RAG sync complete.")
        budget.print_summary()
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="sync only the first N unique documents",
    )
    parser.add_argument("--concurrency", type=int, default=UPLOAD_CONCURRENCY)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.concurrency < 1 or args.concurrency > 8:
        raise SystemExit("--concurrency must be between 1 and 8")
    if args.batch_size < 1 or args.batch_size > 500:
        raise SystemExit("--batch-size must be between 1 and 500")

    sources = load_unique_sources(args.limit)
    estimated_bytes = sum(len(render_source(source).encode("utf-8")) for source in sources)
    print(f"Unique source documents: {len(sources)}")
    print(f"Estimated UTF-8 upload size: {estimated_bytes:,} bytes")
    if args.dry_run:
        manifest = read_manifest()
        pending_uploads = sum(
            manifest_record(manifest, source).get("status") not in {"uploaded", "indexed"}
            for source in sources
        )
        pending_index = sum(
            manifest_record(manifest, source).get("status") == "uploaded" for source in sources
        )
        pending_batches = (pending_uploads + pending_index + args.batch_size - 1) // args.batch_size
        estimated_reservation = (
            pending_uploads * settings.openai_rag_upload_reservation_usd
            + pending_batches * settings.openai_rag_batch_reservation_usd
        )
        print(f"Documents requiring upload: {pending_uploads}")
        print(f"Documents requiring indexing: {pending_index}")
        print(f"Maximum new ledger reservation: ${estimated_reservation:.4f}")
        return

    asyncio.run(sync(args.limit, args.concurrency, args.batch_size))


if __name__ == "__main__":
    main()
