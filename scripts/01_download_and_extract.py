"""
Step 1 of the data pipeline: download the myScheme dataset's PDFs from
Hugging Face and extract raw text from each.

The dataset (shrijayan/gov_myscheme) is a large PDF corpus under text_data/,
not a clean CSV/JSON. The exact file count is read from the repository at run
time because the upstream corpus changes.

Usage:
    python scripts/01_download_and_extract.py

Output:
    data/raw_pdfs_hf_cache/*.pdf (downloaded and resumable)
    data/structured/raw_text.jsonl   (one JSON line per scheme: id, filename, raw_text)

Requires: huggingface_hub, pdfplumber
    pip install huggingface_hub pdfplumber
"""
import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

import pdfplumber
from huggingface_hub import hf_hub_download, list_repo_files

REPO_ID = "shrijayan/gov_myscheme"
REPO_TYPE = "dataset"
RAW_PDF_DIR = Path("data/raw_pdfs")
OUTPUT_PATH = Path("data/structured/raw_text.jsonl")
DOWNLOAD_CONCURRENCY = 6
EXTRACTION_CONCURRENCY = 4


def download_one(filename: str) -> Path:
    cached_path = Path("data/raw_pdfs_hf_cache") / filename
    if cached_path.exists() and cached_path.stat().st_size > 0:
        return cached_path
    local_path = hf_hub_download(
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        filename=filename,
        local_dir="data/raw_pdfs_hf_cache",
    )
    return Path(local_path)


def download_pdfs() -> list[Path]:
    RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
    files = list_repo_files(REPO_ID, repo_type=REPO_TYPE)
    pdf_files = [f for f in files if f.startswith("text_data/") and f.endswith(".pdf")]
    print(f"Found {len(pdf_files)} PDFs in the dataset")

    local_paths: list[Path] = []
    failures: list[tuple[str, Exception]] = []
    with ThreadPoolExecutor(max_workers=DOWNLOAD_CONCURRENCY) as executor:
        futures = {executor.submit(download_one, filename): filename for filename in pdf_files}
        for index, future in enumerate(as_completed(futures), 1):
            filename = futures[future]
            try:
                local_paths.append(future.result())
            except Exception as exc:
                failures.append((filename, exc))
                print(f"  [DOWNLOAD FAIL] {filename}: {exc}", flush=True)
            if index % 50 == 0 or index == len(pdf_files):
                print(f"  ...{index}/{len(pdf_files)} downloaded", flush=True)

    if failures:
        raise SystemExit(
            f"{len(failures)} PDF downloads failed; rerun the step to retry them."
        )
    return sorted(local_paths, key=lambda path: str(path))


def extract_text(pdf_path: Path) -> str:
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_one(pdf_path: Path) -> tuple[Path, str | None, Exception | None]:
    try:
        raw_text = extract_text(pdf_path)
    except Exception as exc:
        return pdf_path, None, exc
    return pdf_path, raw_text, None


def main():
    pdf_paths = download_pdfs()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=EXTRACTION_CONCURRENCY) as executor:
        futures = [executor.submit(extract_one, pdf_path) for pdf_path in pdf_paths]
        with open(OUTPUT_PATH, "w", encoding="utf-8") as out:
            for index, future in enumerate(as_completed(futures), 1):
                pdf_path, raw_text, error = future.result()
                if error is not None:
                    print(
                        f"  [SKIP] {pdf_path.name}: extraction failed ({error})",
                        flush=True,
                    )
                    continue

                if not raw_text or not raw_text.strip():
                    print(
                        f"  [SKIP] {pdf_path.name}: empty extracted text "
                        "(likely scanned image PDF)",
                        flush=True,
                    )
                    continue

                record = {
                    "id": pdf_path.stem,
                    "filename": pdf_path.name,
                    "raw_text": raw_text,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")

                if index % 50 == 0 or index == len(pdf_paths):
                    print(f"  ...{index}/{len(pdf_paths)} extracted", flush=True)

    print(f"Done. Raw text written to {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
