"""
Step 2: cheap keyword pre-filter, run BEFORE the LLM structuring pass (step 3),
so we don't spend LLM calls/credits structuring all 723 schemes when we only
need state #1 + a couple of categories for the initial build.

This is a coarse filter, not the real eligibility logic — it just narrows
~723 schemes down to a candidate list worth the LLM's attention. False
positives are fine (LLM step will sort them out); false negatives are the
risk, so keep the keyword list generous.

Usage:
    python scripts/02_prefilter.py --state Karnataka --category education welfare

Output:
    data/structured/candidates.jsonl
"""
import argparse
import json
from pathlib import Path

INPUT_PATH = Path("data/structured/raw_text.jsonl")
OUTPUT_PATH = Path("data/structured/candidates.jsonl")

# Loose keyword sets — expand as you find real misses during QA.
CATEGORY_KEYWORDS = {
    "education": ["scholarship", "student", "college", "university", "school", "education", "fee reimbursement"],
    "welfare": ["welfare", "pension", "disability", "widow", "senior citizen"],
    "housing": ["housing", "awas", "house construction", "shelter"],
    "agriculture": ["farmer", "agriculture", "kisan", "crop", "irrigation"],
}


def load_records():
    with open(INPUT_PATH, encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def matches(text: str, state: str | None, categories: list[str]) -> bool:
    lower = text.lower()

    # State check: either the specific state is named, or it reads as a
    # central/all-India scheme (no state restriction mentioned at all).
    state_ok = True
    if state:
        state_ok = state.lower() in lower or "all india" in lower or "central government" in lower

    if not categories:
        return state_ok

    category_ok = any(
        keyword in lower
        for cat in categories
        for keyword in CATEGORY_KEYWORDS.get(cat, [cat])
    )
    return state_ok and category_ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default=None, help="e.g. Karnataka")
    parser.add_argument("--category", nargs="*", default=[], help="e.g. education welfare")
    args = parser.parse_args()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    kept, total = 0, 0

    with open(OUTPUT_PATH, "w", encoding="utf-8") as out:
        for record in load_records():
            total += 1
            if matches(record["raw_text"], args.state, args.category):
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                kept += 1

    print(f"Kept {kept}/{total} schemes as candidates -> {OUTPUT_PATH}")
    print("Review this file before running the (paid) LLM structuring step —")
    print("false positives cost a wasted LLM call each, not a correctness bug.")


if __name__ == "__main__":
    main()
