"""Step 3: turn each candidate's raw text into the structured eligibility schema.

The accuracy-critical step. Everything downstream is arithmetic over what this
produces, so a hallucinated income cap here becomes a confident wrong answer
told to a caller who actually qualified.

Two guards against that. The prompt forbids inference — anything not stated
becomes null, which the matcher treats as "not checked" rather than "no
restriction". And every result is validated against the real EligibilityCriteria
contract before it is written, so malformed output fails here rather than
during a call.

Usage:
    python scripts/03_structure_with_llm.py --state-code KA
    python scripts/03_structure_with_llm.py --state-code KA --limit 20
    python scripts/03_structure_with_llm.py --state-code KA --resume

Output:
    data/structured/benefits.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from sahaayak_common import REPO_ROOT, settings, slugify
from sahaayak_contracts import (
    Domain,
    EducationLevel,
    EligibilityCriteria,
    Gender,
    SocialCategory,
)

INPUT_PATH = REPO_ROOT / "data" / "structured" / "candidates.jsonl"
OUTPUT_PATH = REPO_ROOT / "data" / "structured" / "benefits.jsonl"

# Enough parallelism to make 300 documents tolerable, low enough to stay under
# typical rate limits without a backoff dance.
CONCURRENCY = 5

# Source documents run long and the eligibility section is near the top; this
# keeps a single oversized PDF from dominating the bill.
MAX_INPUT_CHARACTERS = 12_000

SYSTEM_PROMPT = f"""You convert Indian government scheme documents into structured JSON.

Extract ONLY what the text explicitly states. Never infer, never guess, never \
fill in what a scheme like this "usually" requires. Use null for anything the \
document does not mention.

This distinction matters: null means "the document is silent", which is treated \
downstream as a condition that is not checked. Inventing a value instead \
produces confident wrong answers for real applicants.

Output strictly valid JSON in this shape:
{{
  "name": string,
  "domain": one of {[d.value for d in Domain]},
  "category": string,
  "description": string,
  "state_code": two-letter state code, or null for central/all-India schemes,
  "eligibility_initial": {{
    "age_min": integer or null,
    "age_max": integer or null,
    "max_annual_family_income_inr": integer rupees or null,
    "category": array from {[c.value for c in SocialCategory]}, or null,
    "gender": one of {[g.value for g in Gender]}, or null,
    "occupation": array of lowercase English nouns, or null,
    "education_level": array from {[e.value for e in EducationLevel]}, or null,
    "min_education_level": one of the same values, or null,
    "enrollment_mode": array from ["regular","distance","correspondence"], or null,
    "state_residency_required": boolean,
    "disability_required": boolean,
    "min_experience_years": integer or null,
    "locations": array of place names, or null,
    "exclusions": array of disqualifying conditions stated in the text
  }},
  "eligibility_renewal": same shape, or null when no separate renewal terms exist,
  "benefits_text": string, what the applicant receives, in plain language,
  "documents_required": array of strings,
  "application_process": string
}}

Use "education_level" for an explicit list of acceptable levels and \
"min_education_level" for a floor such as "Class 10 pass or above". Put \
conditions you cannot express as a field — for example "must not already \
receive another scholarship" — into "exclusions" rather than dropping them."""


class StructuredBenefit(BaseModel):
    name: str
    domain: Domain = Domain.SCHEME
    category: str = ""
    description: str = ""
    state_code: str | None = None
    eligibility_initial: EligibilityCriteria = Field(default_factory=EligibilityCriteria)
    eligibility_renewal: EligibilityCriteria | None = None
    benefits_text: str = ""
    documents_required: list[str] = Field(default_factory=list)
    application_process: str = ""


def load_candidates() -> list[dict]:
    if not INPUT_PATH.exists():
        raise SystemExit(f"{INPUT_PATH} not found — run steps 01 and 02 first.")
    with open(INPUT_PATH, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def already_structured() -> set[str]:
    if not OUTPUT_PATH.exists():
        return set()
    with open(OUTPUT_PATH, encoding="utf-8") as handle:
        return {json.loads(line)["id"] for line in handle if line.strip()}


async def structure_one(
    client: AsyncOpenAI, record: dict, semaphore: asyncio.Semaphore
) -> tuple[str, StructuredBenefit | None, str]:
    async with semaphore:
        try:
            response = await client.chat.completions.create(
                model=settings.openai_structuring_model,
                response_format={"type": "json_object"},
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": record["raw_text"][:MAX_INPUT_CHARACTERS],
                    },
                ],
            )
            payload = json.loads(response.choices[0].message.content or "{}")
            return record["id"], StructuredBenefit.model_validate(payload), ""
        except (json.JSONDecodeError, ValidationError) as exc:
            return record["id"], None, f"invalid output: {exc}"
        except Exception as exc:
            return record["id"], None, f"{exc.__class__.__name__}: {exc}"


async def run(state_code: str, limit: int | None, resume: bool) -> None:
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is not set — this step needs a model.")

    candidates = load_candidates()
    done = already_structured() if resume else set()
    pending = [record for record in candidates if record["id"] not in done]
    if limit:
        pending = pending[:limit]

    if not pending:
        print("Nothing to do — every candidate is already structured.")
        return

    print(
        f"Structuring {len(pending)} candidates with "
        f"{settings.openai_structuring_model} ({len(done)} already done)."
    )

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    semaphore = asyncio.Semaphore(CONCURRENCY)
    tasks = [structure_one(client, record, semaphore) for record in pending]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    written, failed = 0, 0

    with open(OUTPUT_PATH, "a" if resume else "w", encoding="utf-8") as out:
        for coro in asyncio.as_completed(tasks):
            record_id, structured, error = await coro
            if structured is None:
                failed += 1
                print(f"  [FAIL] {record_id}: {error}")
                continue

            row = {
                "id": record_id or slugify(structured.name),
                **structured.model_dump(mode="json"),
                # The LLM is asked for a state code but the run is already
                # scoped to one, so the caller's flag wins for anything the
                # document left ambiguous.
                "state_code": structured.state_code or state_code,
                "source_url": f"https://www.myscheme.gov.in/schemes/{record_id}",
                "last_verified_date": date.today().isoformat(),
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
            print(f"  [OK] {structured.name}")

    print(f"\nStructured {written} schemes, {failed} failed -> {OUTPUT_PATH}")
    print("Next: spot-check a sample against the source PDFs before seeding.")
    print(f"  python scripts/05_spotcheck.py --n {max(5, written // 5)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-code", required=True, help="e.g. KA")
    parser.add_argument("--limit", type=int, default=None, help="structure only the first N")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="skip candidates already present in benefits.jsonl and append",
    )
    args = parser.parse_args()
    asyncio.run(run(args.state_code, args.limit, args.resume))


if __name__ == "__main__":
    main()
