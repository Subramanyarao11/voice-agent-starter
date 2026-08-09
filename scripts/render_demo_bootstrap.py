"""Bootstrap the Render Free demo database after migrations.

Migrations alone leave zero benefits, so visitors see "0 benefits loaded" and
cannot get eligibility matches. Launch languages are also limited to en/hi/kn
until release evidence is approved.

When RENDER_DEMO_BOOTSTRAP=true (set in render.yaml), this script:

1. Seeds ``data/demo/benefits.jsonl`` (committed demo catalog) if present.
2. Opens all planned languages via ``open_demo_language_catalog`` when
   RENDER_DEMO_OPEN_CATALOG=true.

The API lifespan also re-applies language open after ``ensure_reference_data``,
because that merge used to reset planned locales to inactive on every boot.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError
from sqlmodel import func, select

from sahaayak_agent.bootstrap import ensure_reference_data, open_demo_language_catalog
from sahaayak_common import (
    REPO_ROOT,
    Benefit,
    init_db,
    session_scope,
)
from sahaayak_contracts import VerificationStatus

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from seed_demo import DEMO_BENEFITS  # noqa: E402

DEMO_BENEFITS_FILE = REPO_ROOT / "data" / "demo" / "benefits.jsonl"


def _truthy(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _active_benefit_count() -> int:
    with session_scope() as db:
        return int(
            db.exec(
                select(func.count()).select_from(Benefit).where(Benefit.is_active.is_(True))
            ).one()
            or 0
        )


def _seed_from_demo_jsonl(path: Path) -> tuple[int, int]:
    """Load validated rows using the pipeline seed helpers."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "seed_db_helpers", _SCRIPTS_DIR / "04_seed_db.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load scripts/04_seed_db.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    seeded = 0
    skipped = 0
    with path.open(encoding="utf-8") as handle, session_scope() as db:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                row["is_active"] = True
                benefit = module.build_benefit(row)
                benefit.is_active = True
                module.import_benefit(db, benefit)
                seeded += 1
            except (json.JSONDecodeError, ValidationError, KeyError, ValueError) as exc:
                skipped += 1
                print(f"  [SKIP] {path.name}:{line_number}: {exc}")
    return seeded, skipped


def _seed_demo_benefits_fallback() -> int:
    with session_scope() as db:
        for entry in DEMO_BENEFITS:
            db.merge(
                Benefit(
                    **entry,
                    eligibility_renewal=None,
                    last_verified_date=date.today(),
                    verification_status=VerificationStatus.ILLUSTRATIVE,
                    source_title="myScheme reference (illustrative demo)",
                    source_document_url=entry.get("source_url", ""),
                    is_active=True,
                )
            )
    return len(DEMO_BENEFITS)


def main() -> None:
    if not _truthy("RENDER_DEMO_BOOTSTRAP", "false"):
        print("RENDER_DEMO_BOOTSTRAP disabled; skipping demo bootstrap.")
        return

    init_db()
    ensure_reference_data()

    before = _active_benefit_count()
    if DEMO_BENEFITS_FILE.exists():
        seeded, skipped = _seed_from_demo_jsonl(DEMO_BENEFITS_FILE)
        print(
            f"Merged {seeded} benefits from {DEMO_BENEFITS_FILE} "
            f"({skipped} skipped; active before={before})."
        )
    elif before == 0:
        seeded = _seed_demo_benefits_fallback()
        print(f"Seeded {seeded} illustrative demo benefits (fallback).")
    else:
        print(f"Active benefits already present ({before}); no demo file in image.")

    if _truthy("RENDER_DEMO_OPEN_CATALOG", "true"):
        open_demo_language_catalog()
        print(
            "Opened demo catalog: all languages activated, "
            "ten_language_rollout on, state_rollout unrestricted."
        )
    else:
        print("RENDER_DEMO_OPEN_CATALOG disabled; launch languages only (en/hi/kn).")


if __name__ == "__main__":
    main()
