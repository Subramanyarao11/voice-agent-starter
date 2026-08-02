"""
Step 4: load structured schemes (from step 3) into the Benefit table.

Usage:
    python scripts/04_seed_db.py
"""
import json
from pathlib import Path

from sqlmodel import Session

from app.core.db import engine, init_db
from app.models.core import Benefit, Domain

INPUT_PATH = Path("data/structured/benefits.jsonl")


def main():
    init_db()

    with open(INPUT_PATH, encoding="utf-8") as f, Session(engine) as session:
        count = 0
        for line in f:
            row = json.loads(line)
            benefit = Benefit(
                id=row["id"],
                domain=Domain(row["domain"]),
                name=row["name"],
                state_code=row["state_code"],
                category=row["category"],
                description=row["description"],
                eligibility_initial=row["eligibility_initial"],
                eligibility_renewal=row.get("eligibility_renewal"),
                benefits_text=row["benefits_text"],
                documents_required=row["documents_required"],
                application_process=row["application_process"],
                source_url=row["source_url"],
                last_verified_date=row["last_verified_date"],
            )
            session.merge(benefit)  # merge = insert or update, safe to re-run
            count += 1

        session.commit()

    print(f"Seeded {count} benefits into the database.")


if __name__ == "__main__":
    main()
