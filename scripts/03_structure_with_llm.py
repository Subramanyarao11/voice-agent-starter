"""
Step 3: the important one. Turns each candidate scheme's raw PDF text into
our structured schema (matches app/schemas/eligibility.py and
app/models/core.py's Benefit table) — numeric income caps as integers,
category as a controlled enum list, age as min/max ints, etc. — instead of
leaving eligibility as free text the agent would have to guess over.

Spot-check ~20% of the output against the source PDF before trusting it
(see README Day 1 checklist). This step is the highest-leverage 2-3 hours
of the whole build — don't rush it.

Usage:
    python scripts/03_structure_with_llm.py --state-code KA

Output:
    data/structured/benefits.jsonl   (ready to load via scripts/04_seed_db.py)
"""
import argparse
import json
from datetime import date
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from app.core.config import settings

INPUT_PATH = Path("data/structured/candidates.jsonl")
OUTPUT_PATH = Path("data/structured/benefits.jsonl")

client = OpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT = """You convert Indian government scheme documents into structured JSON.
Extract ONLY what is explicitly stated in the text — never infer or guess a number,
category, or condition that isn't written. Use null for anything not mentioned.

Output strictly valid JSON matching this schema:
{
  "name": string,
  "domain": "scheme" | "scholarship" | "job",
  "category": string,               // e.g. "Education & Learning", "Housing", "Agriculture"
  "description": string,            // 1-2 sentences, your own summary
  "state_code": string | null,      // null if central/all-India, else e.g. "KA"
  "eligibility_initial": {
    "age_min": int | null,
    "age_max": int | null,
    "max_annual_family_income_inr": int | null,
    "category": [string] | null,    // subset of ["SC","ST","OBC","EWS","General"]
    "gender": string | null,
    "occupation": [string] | null,
    "education_level": [string] | null,
    "enrollment_mode": [string] | null,
    "state_residency_required": bool,
    "exclusions": [string]
  },
  "eligibility_renewal": <same shape as eligibility_initial, or null if no separate renewal conditions exist>,
  "benefits_text": string,          // what the applicant receives, in plain language
  "documents_required": [string],
  "application_process": string
}"""


class StructuredBenefit(BaseModel):
    name: str
    domain: str
    category: str
    description: str
    state_code: str | None
    eligibility_initial: dict
    eligibility_renewal: dict | None
    benefits_text: str
    documents_required: list[str]
    application_process: str


def structure_one(raw_text: str) -> StructuredBenefit | None:
    response = client.chat.completions.create(
        model="gpt-4o",  # use a strong model here — this is the accuracy-critical step
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text[:12000]},  # guard against oversized docs
        ],
        temperature=0,
    )
    try:
        parsed = json.loads(response.choices[0].message.content)
        return StructuredBenefit(**parsed)
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"  [PARSE FAIL] {e}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-code", required=True, help="e.g. KA — tagged onto every output row")
    args = parser.parse_args()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    kept, failed = 0, 0

    with open(INPUT_PATH, encoding="utf-8") as f_in, open(OUTPUT_PATH, "w", encoding="utf-8") as f_out:
        for line in f_in:
            record = json.loads(line)
            structured = structure_one(record["raw_text"])
            if structured is None:
                failed += 1
                continue

            benefit_row = {
                "id": record["id"],
                **structured.model_dump(),
                "source_url": f"https://www.myscheme.gov.in/schemes/{record['id']}",
                "last_verified_date": date.today().isoformat(),
            }
            f_out.write(json.dumps(benefit_row, ensure_ascii=False) + "\n")
            kept += 1
            print(f"  [OK] {structured.name}")

    print(f"\nStructured {kept} schemes ({failed} failed to parse) -> {OUTPUT_PATH}")
    print("Next: spot-check ~20% of these against the source PDFs, then run 04_seed_db.py")


if __name__ == "__main__":
    main()
