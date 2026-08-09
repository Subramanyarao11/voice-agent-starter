from __future__ import annotations

import importlib
import json


def test_rag_loader_includes_job_source_text_with_provenance(tmp_path, monkeypatch):
    module = importlib.import_module("scripts.07_sync_openai_vector_store")
    myscheme_path = tmp_path / "raw_text.jsonl"
    job_path = tmp_path / "job_sources.jsonl"
    myscheme_path.write_text(
        json.dumps(
            {
                "id": "demo-scheme",
                "filename": "demo.pdf",
                "raw_text": "A scheme source",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    job_path.write_text(
        json.dumps(
            {
                "source_id": "upsc-notice",
                "filename": "notice.pdf",
                "raw_text": "Closing date 28-08-2026.",
                "source_hash": "pdf-hash",
                "source_url": "https://www.upsc.gov.in/notice.pdf",
                "source_title": "UPSC recruitment notice",
                "dataset": "upsc_recruitment",
                "verification": "raw_machine_extracted",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "INPUT_PATH", myscheme_path)
    monkeypatch.setattr(module, "JOB_INPUT_PATH", job_path)

    sources = module.load_unique_sources(dataset="upsc_recruitment")

    assert len(sources) == 1
    assert sources[0].dataset == "upsc_recruitment"
    assert sources[0].source_url == "https://www.upsc.gov.in/notice.pdf"
    assert "Verification status: raw_machine_extracted" in module.render_source(sources[0])


def test_rag_loader_preserves_myscheme_source_url_and_avoids_fake_routes(tmp_path, monkeypatch):
    module = importlib.import_module("scripts.07_sync_openai_vector_store")
    source_path = tmp_path / "raw_text.jsonl"
    source_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "captured-scheme",
                        "filename": "captured.pdf",
                        "raw_text": "Captured source",
                        "source_url": "https://department.gov.in/notice/123.pdf",
                    }
                ),
                json.dumps(
                    {
                        "id": "scheme copy export",
                        "filename": "scheme copy export.pdf",
                        "raw_text": "Unresolved export source",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "INPUT_PATH", source_path)

    sources = module.load_unique_sources(dataset="myscheme")

    by_id = {source.source_id: source for source in sources}
    assert by_id["captured-scheme"].source_url == "https://department.gov.in/notice/123.pdf"
    assert by_id["scheme copy export"].source_url == "https://www.myscheme.gov.in/"
