"""Run one source-grounded query against the persistent OpenAI Vector Store.

Usage:
    uv run python scripts/08_query_rag.py "What scholarships are available for students?"
"""

from __future__ import annotations

import argparse
import asyncio

from sahaayak_agent.retrieval import OpenAIRetrieval


async def run(query: str, max_results: int) -> None:
    rag = OpenAIRetrieval()
    try:
        response = await rag.answer(query, max_results=max_results)
    finally:
        await rag.close()

    print(response.answer)
    print("\nSources:")
    for index, source in enumerate(response.sources, 1):
        print(f"[{index}] {source.source_id} score={source.score:.3f}")
        print(f"    {source.source_url}")
        print(f"    {source.excerpt[:300].replace(chr(10), ' ')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--max-results", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(run(args.query, args.max_results))


if __name__ == "__main__":
    main()
