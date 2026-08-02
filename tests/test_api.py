"""HTTP-level tests.

Mostly checking the contract the web client depends on, plus that the routes
degrade sensibly when optional infrastructure is absent — which, in this test
environment, it entirely is.
"""

from __future__ import annotations


def test_health_reports_degraded_capabilities_without_failing(client):
    """A text-only deployment is supported and must not look broken."""
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["cache"] == "memory"
    assert body["text_to_speech"] is False
    assert set(body["languages"]) >= {"en", "hi", "kn"}


def test_catalog_is_read_from_the_database(client):
    languages = {row["code"] for row in client.get("/api/languages").json()}
    assert {"kn", "hi", "en"} <= languages

    states = {row["code"]: row for row in client.get("/api/states").json()}
    assert states["KA"]["is_active"] is True
    # A state whose language is not served yet is listed but inactive, so the
    # expansion path is visible without over-claiming coverage.
    assert states["TN"]["is_active"] is False


def test_coverage_counts_loaded_benefits(client):
    body = client.get("/api/coverage").json()
    assert body["total"] > 0
    assert "scholarship" in body["by_domain"]
    assert body["verified_total"] == 0
    assert body["illustrative_total"] == body["total"]
    assert body["last_data_update"]


def test_benefit_detail_exposes_provenance(client):
    response = client.get("/api/benefits/demo-csss-cus")
    assert response.status_code == 200
    body = response.json()
    assert body["verification_status"] == "illustrative"
    assert body["source_document_url"].startswith("https://www.myscheme.gov.in/")
    assert body["verified_at"] is None
    assert client.get("/api/benefits/does-not-exist").status_code == 404


def test_a_text_turn_returns_a_question(client):
    response = client.post(
        "/api/turns",
        json={
            "caller_id": "+919000000001",
            "text": "I need a scholarship",
            "language_code": "en",
            "state_code": "KA",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pending_slot"] == "age"
    assert body["response_text"]
    assert response.headers["X-Request-ID"]


def test_match_response_carries_verification_status_and_source(client):
    payload = {
        "caller_id": "+919000000010",
        "language_code": "en",
        "state_code": "KA",
    }
    client.post(
        "/api/turns",
        json={**payload, "text": "I need a scholarship"},
    )
    client.post("/api/turns", json={**payload, "text": "22"})
    response = client.post(
        "/api/turns",
        json={**payload, "text": "2 lakh and regular degree college"},
    )
    assert response.status_code == 200
    matches = response.json()["matches"]
    assert matches
    assert {match["verification_status"] for match in matches} == {"illustrative"}
    assert all(match["source_document_url"] for match in matches)


def test_an_inbound_request_id_is_echoed_back(client):
    """So a telephony provider's trace and ours line up on one identifier."""
    response = client.get("/health", headers={"X-Request-ID": "trace-me"})
    assert response.headers["X-Request-ID"] == "trace-me"


def test_session_and_transcript_are_retrievable(client):
    caller = "+919000000002"
    client.post(
        "/api/turns",
        json={"caller_id": caller, "text": "I need a scholarship", "language_code": "en"},
    )
    client.post("/api/turns", json={"caller_id": caller, "text": "22"})

    session = client.get(f"/api/sessions/{caller}").json()
    assert session["turn_count"] == 2
    assert session["profile"]["age"] == 22
    assert session["conversation_state"]["domain"] == "scholarship"

    transcript = client.get(f"/api/sessions/{caller}/transcript").json()
    assert [turn["role"] for turn in transcript[:2]] == ["caller", "agent"]


def test_unknown_caller_is_a_404_not_an_empty_session(client):
    assert client.get("/api/sessions/+910000000000").status_code == 404


def test_a_caller_can_have_their_record_deleted(client):
    caller = "+919000000003"
    client.post(
        "/api/turns",
        json={"caller_id": caller, "text": "I need a scholarship", "language_code": "en"},
    )
    assert client.delete(f"/api/sessions/{caller}").status_code == 204
    assert client.get(f"/api/sessions/{caller}").status_code == 404


def test_escalations_are_recorded_as_tickets(client):
    client.post(
        "/api/turns",
        json={
            "caller_id": "+919000000004",
            "text": "I want to talk to a person",
            "language_code": "en",
        },
    )
    tickets = client.get("/api/escalations").json()
    assert any(ticket["reason"] == "caller_requested" for ticket in tickets)

    ticket_id = tickets[0]["id"]
    resolved = client.post(f"/api/escalations/{ticket_id}/resolve").json()
    assert resolved["status"] == "resolved"


def test_voice_turn_reports_unavailable_rather_than_erroring(client):
    """With no key configured this is a deployment state, not a server fault."""
    response = client.post(
        "/api/voice/turns",
        files={"audio": ("turn.wav", b"not-real-audio", "audio/wav")},
        data={"caller_id": "+919000000005", "language_code": "en"},
    )
    assert response.status_code == 503


def test_empty_audio_is_rejected(client):
    response = client.post(
        "/api/voice/turns",
        files={"audio": ("turn.wav", b"", "audio/wav")},
        data={"caller_id": "+919000000006"},
    )
    assert response.status_code == 400


def test_openapi_schema_is_generated(client):
    schema = client.get("/api/openapi.json").json()
    assert "/api/turns" in schema["paths"]
