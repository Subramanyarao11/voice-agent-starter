"""Offline tests for the source-grounded retrieval boundary."""

from __future__ import annotations

from sahaayak_agent.retrieval import deduplicate_sources, format_sources, parse_search_result


def test_parse_search_result_preserves_source_provenance_and_text():
    source = parse_search_result(
        {
            "filename": "scheme.txt",
            "score": 0.875,
            "attributes": {
                "source_id": "scheme-1",
                "source_url": "https://example.test/scheme-1",
                "verification": "raw_extracted",
            },
            "content": [
                {"type": "text", "text": "Benefits: monthly support."},
                {"type": "text", "text": "Eligibility: student."},
            ],
        }
    )

    assert source.source_id == "scheme-1"
    assert source.filename == "scheme.txt"
    assert source.score == 0.875
    assert source.source_url == "https://example.test/scheme-1"
    assert source.excerpt == "Benefits: monthly support.\nEligibility: student."
    assert source.attributes["verification"] == "raw_extracted"


def test_format_sources_bounds_context_and_numbers_each_source():
    sources = parse_search_result(
        {
            "filename": "first.txt",
            "score": 0.9,
            "attributes": {"source_id": "first"},
            "content": [{"text": "A" * 700}],
        }
    ), parse_search_result(
        {
            "filename": "second.txt",
            "score": 0.8,
            "attributes": {"source_id": "second"},
            "content": [{"text": "B" * 700}],
        }
    )

    context = format_sources(list(sources), max_characters=1_000)

    assert "[Source 1]" in context
    assert "first.txt" in context
    assert "[Source 2]" not in context
    assert len(context) <= 1_000


def test_deduplicate_sources_merges_chunks_from_the_same_document():
    first = parse_search_result(
        {
            "filename": "same.txt",
            "score": 0.7,
            "attributes": {"source_id": "same"},
            "content": [{"text": "First relevant passage."}],
        }
    )
    second = parse_search_result(
        {
            "filename": "same.txt",
            "score": 0.9,
            "attributes": {"source_id": "same"},
            "content": [{"text": "Second relevant passage."}],
        }
    )

    sources = deduplicate_sources([first, second])

    assert len(sources) == 1
    assert sources[0].score == 0.9
    assert "First relevant passage." in sources[0].excerpt
    assert "Second relevant passage." in sources[0].excerpt
