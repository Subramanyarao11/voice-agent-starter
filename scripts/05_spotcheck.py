"""
Spot-check helper for the Day 1 checklist ("spot-check ~20% of structured
output against source"). Pulls N random rows from benefits.jsonl, finds each
one's original raw text, and prints them side-by-side so you're not manually
hunting through data/raw_pdfs_hf_cache/ for the right file every time.

Usage:
    python scripts/05_spotcheck.py                # 10 random rows (default)
    python scripts/05_spotcheck.py --n 20
    python scripts/05_spotcheck.py --seed 42       # reproducible sample
    python scripts/05_spotcheck.py --id csss-cus   # check one specific scheme

For each row, eyeball:
  - Is every number (age, income) actually in the source text, not invented?
  - Is `category` (SC/ST/OBC/EWS/General) actually stated, not assumed?
  - Does `state_code` match what the text says (or null if genuinely central)?
  - Are `exclusions` complete, or did the LLM drop a caveat?

Mark failures by re-running scheme IDs through step 3 individually, or fix
by hand directly in benefits.jsonl — either is fine for a small candidate set.
"""
import argparse
import json
import random
import textwrap
from pathlib import Path

RAW_TEXT_PATH = Path("data/structured/raw_text.jsonl")
BENEFITS_PATH = Path("data/structured/benefits.jsonl")


def load_jsonl(path: Path) -> dict[str, dict]:
    records = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            records[row["id"]] = row
    return records


def wrap(text: str, width: int = 100) -> str:
    return "\n".join(textwrap.wrap(text, width=width)) if text else "(empty)"


def print_row(structured: dict, raw_text: str):
    sep = "=" * 100
    print(sep)
    print(f"ID: {structured['id']}   |   {structured['name']}")
    print(sep)

    print("\n--- STRUCTURED (check this) ---")
    body = {k: v for k, v in structured.items() if k != "id"}
    print(json.dumps(body, indent=2, ensure_ascii=False))

    print("\n--- SOURCE TEXT (ground truth) ---")
    print(wrap(raw_text[:2500]))
    if len(raw_text) > 2500:
        remaining = len(raw_text) - 2500
        print(f"...[{remaining} more characters truncated — open the PDF directly if needed]")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10, help="number of random rows to check")
    parser.add_argument(
        "--seed", type=int, default=None, help="random seed for reproducible sampling"
    )
    parser.add_argument(
        "--id", default=None, help="check one specific scheme id instead of sampling"
    )
    args = parser.parse_args()

    if not BENEFITS_PATH.exists() or not RAW_TEXT_PATH.exists():
        print("Missing data/structured/benefits.jsonl or raw_text.jsonl —")
        print("run steps 01, 02, 03 first.")
        return

    structured = load_jsonl(BENEFITS_PATH)
    raw = load_jsonl(RAW_TEXT_PATH)

    if args.id:
        if args.id not in structured:
            print(f"'{args.id}' not found in benefits.jsonl")
            return
        ids_to_check = [args.id]
    else:
        if args.seed is not None:
            random.seed(args.seed)
        ids_to_check = random.sample(list(structured.keys()), min(args.n, len(structured)))

    print(f"Spot-checking {len(ids_to_check)} of {len(structured)} structured schemes\n")

    for scheme_id in ids_to_check:
        raw_record = raw.get(scheme_id)
        raw_text = (
            raw_record["raw_text"]
            if raw_record
            else "(raw text not found — check the id matches)"
        )
        print_row(structured[scheme_id], raw_text)

    print("=" * 100)
    print(f"Reviewed {len(ids_to_check)} rows. Note any failures and either:")
    print("  - fix directly in data/structured/benefits.jsonl, or")
    print("  - re-run: python scripts/03_structure_with_llm.py for just that candidate")


if __name__ == "__main__":
    main()
