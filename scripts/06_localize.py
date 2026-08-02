"""Step 6: pre-translate each benefit's summary into every served language.

Done at ingestion rather than during a call, for two reasons. Translating live
adds a model round-trip to every result on a phone call, where the caller hears
every millisecond. And a translation produced once can be reviewed by a native
speaker, whereas one generated per call cannot.

Usage:
    python scripts/06_localize.py --languages kn hi
    python scripts/06_localize.py --languages kn --limit 20 --overwrite

Reads and writes the `localized_summary` column in place, so it is safe to
re-run and will skip anything already translated unless --overwrite is given.
"""

from __future__ import annotations

import argparse
import asyncio

from openai import AsyncOpenAI
from sqlmodel import select

from sahaayak_agent.languages import DEFAULT_CATALOG
from sahaayak_common import (
    Benefit,
    BudgetError,
    BudgetExceeded,
    BudgetReservation,
    OpenAIBudgetLedger,
    get_logger,
    session_scope,
    settings,
)

log = get_logger(__name__)

CONCURRENCY = 2
MAX_OUTPUT_TOKENS = 300

SYSTEM_PROMPT = """You translate short descriptions of Indian government \
benefits for a voice assistant that reads them aloud to callers.

Write for the ear, not the page:
- Use everyday spoken vocabulary, not formal administrative register.
- Keep it to one or two short sentences.
- Keep scheme names, and amounts in figures, as they are.
- Do not add information that is not in the source text.

Reply with the translation only, no preamble and no quotation marks."""


async def translate(
    client: AsyncOpenAI,
    text: str,
    language_name: str,
    semaphore: asyncio.Semaphore,
    budget: OpenAIBudgetLedger,
    operation: str,
) -> str:
    async with semaphore:
        reservation: BudgetReservation | None = None
        try:
            user_prompt = f"Translate into {language_name}:\n\n{text}"
            reservation = budget.reserve_chat(
                model=settings.openai_reasoning_model,
                input_characters=len(SYSTEM_PROMPT) + len(user_prompt),
                max_output_tokens=MAX_OUTPUT_TOKENS,
                operation=operation,
            )
            response = await client.chat.completions.create(
                model=settings.openai_reasoning_model,
                temperature=0.2,
                max_completion_tokens=MAX_OUTPUT_TOKENS,
                n=1,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            budget.record_chat_response(reservation, response)
            return (response.choices[0].message.content or "").strip()
        except BudgetExceeded:
            raise
        except BudgetError:
            raise
        except Exception as exc:
            if reservation is not None:
                budget.record_failure(reservation, exc)
            raise


async def run(language_codes: list[str], limit: int | None, overwrite: bool) -> None:
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is not set — this step needs a model.")

    targets = [
        profile
        for profile in DEFAULT_CATALOG.profiles
        if profile.code in language_codes and profile.code != "en"
    ]
    if not targets:
        raise SystemExit(f"No known languages among {language_codes}.")

    try:
        budget = OpenAIBudgetLedger(
            settings.openai_budget_usd,
            settings.resolved_openai_budget_ledger_path,
        )
    except BudgetError as exc:
        raise SystemExit(str(exc)) from exc

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    semaphore = asyncio.Semaphore(CONCURRENCY)

    with session_scope() as db:
        benefits = list(db.exec(select(Benefit)).all())
        if limit:
            benefits = benefits[:limit]

        jobs = []
        for benefit in benefits:
            source = benefit.description or benefit.benefits_text
            if not source.strip():
                continue
            for profile in targets:
                existing = (benefit.localized_summary or {}).get(profile.code)
                if existing and not overwrite:
                    continue
                jobs.append((benefit, profile, source))

        if not jobs:
            print("Every benefit is already translated. Use --overwrite to redo them.")
            budget.print_summary()
            return

        print(f"Translating {len(jobs)} summaries across {len(targets)} languages.")

        results = await asyncio.gather(
            *(
                translate(
                    client,
                    source,
                    p.name,
                    semaphore,
                    budget,
                    f"localize:{benefit.id}:{p.code}",
                )
                for benefit, p, source in jobs
            ),
            return_exceptions=True,
        )

        written, failed = 0, 0
        for (benefit, profile, _), result in zip(jobs, results, strict=True):
            if isinstance(result, Exception) or not result:
                failed += 1
                log.warning(
                    "translation_failed", benefit_id=benefit.id, language=profile.code
                )
                continue
            # Reassigned rather than mutated in place so the change is tracked
            # even for rows loaded before MutableDict saw them.
            summary = dict(benefit.localized_summary or {})
            summary[profile.code] = result
            benefit.localized_summary = summary
            db.add(benefit)
            written += 1

    await client.close()
    print(f"Translated {written} summaries ({failed} failed).")
    budget.print_summary()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--languages", nargs="+", default=["kn", "hi"])
    parser.add_argument("--limit", type=int, default=settings.openai_pipeline_max_records)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.languages, args.limit, args.overwrite))


if __name__ == "__main__":
    main()
