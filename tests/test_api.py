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
    language_rows = {row["code"]: row for row in client.get("/api/languages").json()}
    assert language_rows["ta"]["is_active"] is False
    assert language_rows["bn"]["is_active"] is False


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


def test_job_detail_exposes_posting_metadata(client):
    response = client.get("/api/benefits/demo-ka-anganwadi-helper")
    assert response.status_code == 200
    body = response.json()
    assert body["domain"] == "job"
    assert body["job_metadata"]["employer"]
    assert body["job_metadata"]["source_kind"] == "illustrative_demo"


def test_guest_can_report_incorrect_benefit_information_and_admin_can_close_it(
    client, guest_session
):
    from sahaayak_common import BenefitIssueReport, session_scope

    session = guest_session()
    response = client.post(
        "/api/benefits/demo-csss-cus/reports",
        json={
            "category": "eligibility",
            "description": "The official source appears to show a different income limit.",
        },
        headers=session["headers"],
    )
    assert response.status_code == 201
    report_id = response.json()["id"]

    try:
        reports = client.get("/api/admin/benefit-reports?status=open").json()
        report = next(item for item in reports if item["id"] == report_id)
        assert report["benefit_name"].startswith("Central Sector Scheme of Scholarship")
        assert report["description"].startswith("The official source")

        updated = client.post(
            f"/api/admin/benefit-reports/{report_id}",
            json={
                "status": "resolved",
                "reason": "Checked the linked official source",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "resolved"
    finally:
        with session_scope() as db:
            row = db.get(BenefitIssueReport, report_id)
            if row is not None:
                db.delete(row)


def test_a_text_turn_returns_a_question(client, guest_session):
    session = guest_session()
    response = client.post(
        "/api/turns",
        json={
            "text": "I need a scholarship",
            "language_code": "en",
            "state_code": "KA",
        },
        headers=session["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pending_slot"] == "age"
    assert body["response_text"]
    assert response.headers["X-Request-ID"]


def test_guest_session_token_is_required_and_cannot_cross_session(client, guest_session):
    from sahaayak_api.browser_auth import token_digest
    from sahaayak_common import UserSession, session_scope

    first = guest_session()
    second = guest_session()
    body = {"text": "I need a scholarship", "language_code": "en", "state_code": "KA"}

    assert client.post("/api/turns", json=body).status_code == 401
    assert client.post("/api/turns", json=body, headers=first["headers"]).status_code == 200
    assert client.get(
        f"/api/sessions/{first['session_id']}", headers=second["headers"]
    ).status_code == 404
    assert first["access_token"] not in client.get(
        f"/api/sessions/{first['session_id']}", headers=first["headers"]
    ).text
    with session_scope() as db:
        row = db.get(UserSession, first["session_id"])
        assert row is not None
        assert row.access_token_hash == token_digest(first["access_token"])
        assert first["access_token"] not in row.phone_or_session_id


def test_text_turn_rate_limit_returns_retry_headers(client, guest_session, monkeypatch):
    from sahaayak_common import settings

    monkeypatch.setattr(settings, "rate_limit_text_per_session", 1)
    session = guest_session()
    body = {"text": "I need a scholarship", "language_code": "en", "state_code": "KA"}
    assert client.post("/api/turns", json=body, headers=session["headers"]).status_code == 200
    limited = client.post("/api/turns", json=body, headers=session["headers"])
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]
    assert limited.headers["X-RateLimit-Limit"] == "1"


def test_daily_guest_text_limit_is_enforced(client, guest_session, monkeypatch):
    from sahaayak_common import settings

    monkeypatch.setattr(settings, "rate_limit_text_per_session_per_day", 1)
    monkeypatch.setattr(settings, "rate_limit_text_per_ip_per_day", 100)
    session = guest_session()
    body = {"text": "I need a scholarship", "language_code": "en", "state_code": "KA"}
    assert client.post("/api/turns", json=body, headers=session["headers"]).status_code == 200
    limited = client.post("/api/turns", json=body, headers=session["headers"])
    assert limited.status_code == 429
    assert int(limited.headers["X-RateLimit-Reset"]) > 0


def test_out_of_scope_turn_is_fixed_and_does_not_use_general_chat(client, guest_session):
    session = guest_session()
    response = client.post(
        "/api/turns",
        json={
            "text": "write code to apply for this scholarship",
            "language_code": "en",
            "state_code": "KA",
        },
        headers=session["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matches"] == []
    assert body["sources"] == []
    assert "government schemes" in body["response_text"]


def test_security_headers_are_present_on_api_responses(client):
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "microphone=(self)" in response.headers["Permissions-Policy"]


def test_production_rate_limiter_fails_closed_without_redis(monkeypatch):
    import asyncio

    from fastapi import HTTPException
    from starlette.requests import Request

    from sahaayak_api.rate_limit import enforce_rate_limit, reset_rate_limiter
    from sahaayak_common import settings

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/turns",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
        }
    )
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "rate_limit_key_salt", "test-only-salt")
    reset_rate_limiter()
    try:
        try:
            asyncio.run(
                enforce_rate_limit(request, session_id=None, bucket="session_create")
            )
        except HTTPException as exc:
            assert exc.status_code == 503
        else:  # pragma: no cover - documents the fail-closed expectation
            raise AssertionError("production limiter unexpectedly allowed a request")
    finally:
        reset_rate_limiter()


def test_match_response_carries_verification_status_and_source(client, guest_session):
    session = guest_session()
    payload = {
        "language_code": "en",
        "state_code": "KA",
    }
    client.post(
        "/api/turns",
        json={**payload, "text": "I need a scholarship"},
        headers=session["headers"],
    )
    client.post("/api/turns", json={**payload, "text": "22"}, headers=session["headers"])
    response = client.post(
        "/api/turns",
        json={**payload, "text": "2 lakh and regular degree college"},
        headers=session["headers"],
    )
    assert response.status_code == 200
    matches = response.json()["matches"]
    assert matches
    assert {match["verification_status"] for match in matches} == {"illustrative"}
    assert all(match["source_document_url"] for match in matches)
    assert all("criteria" in match and "caveats" in match for match in matches)
    assert any(
        criterion["status"] in {"pass", "unknown"}
        for match in matches
        for criterion in match["criteria"]
    )


def test_an_inbound_request_id_is_echoed_back(client):
    """So a telephony provider's trace and ours line up on one identifier."""
    response = client.get("/health", headers={"X-Request-ID": "trace-me"})
    assert response.headers["X-Request-ID"] == "trace-me"


def test_readiness_and_metrics_are_safe_operational_surfaces(client):
    readiness = client.get("/readyz")
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "ready"
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "sahaayak_database_up 1" in metrics.text
    assert "session_id" not in metrics.text


def test_guest_can_save_benefit_and_schedule_private_reminder(client, guest_session):
    from datetime import UTC, datetime, timedelta

    session = guest_session()
    saved = client.post(
        f"/api/sessions/{session['session_id']}/saved-benefits",
        json={"benefit_id": "demo-csss-cus"},
        headers=session["headers"],
    )
    assert saved.status_code == 201
    assert saved.json()["benefit_id"] == "demo-csss-cus"

    due_at = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    reminder = client.post(
        f"/api/sessions/{session['session_id']}/reminders",
        json={"benefit_id": "demo-csss-cus", "due_at": due_at},
        headers=session["headers"],
    )
    assert reminder.status_code == 201
    assert reminder.json()["status"] == "scheduled"
    assert len(
        client.get(
            f"/api/sessions/{session['session_id']}/saved-benefits",
            headers=session["headers"],
        ).json()
    ) == 1


def test_telephony_is_disabled_until_a_provider_secret_is_configured(client):
    session = client.post(
        "/api/telephony/turns",
        files={"audio": ("turn.wav", b"not-real-audio", "audio/wav")},
        data={"caller_id": "+910000000000", "language_code": "en"},
    )
    assert session.status_code == 404


def test_session_and_transcript_are_retrievable(client, guest_session):
    session = guest_session()
    client.post(
        "/api/turns",
        json={"text": "I need a scholarship", "language_code": "en"},
        headers=session["headers"],
    )
    client.post("/api/turns", json={"text": "22"}, headers=session["headers"])

    session_body = client.get(
        f"/api/sessions/{session['session_id']}", headers=session["headers"]
    ).json()
    assert session_body["turn_count"] == 2
    assert session_body["profile"]["age"] == 22
    assert session_body["conversation_state"]["domain"] == "scholarship"

    transcript = client.get(
        f"/api/sessions/{session['session_id']}/transcript", headers=session["headers"]
    ).json()
    assert [turn["role"] for turn in transcript[:2]] == ["caller", "agent"]


def test_unknown_caller_is_a_404_not_an_empty_session(client, guest_session):
    session = guest_session()
    assert client.get(
        "/api/sessions/ses_unknown", headers=session["headers"]
    ).status_code == 404


def test_a_caller_can_have_their_record_deleted(client, guest_session):
    session = guest_session()
    client.post(
        "/api/turns",
        json={"text": "I need a scholarship", "language_code": "en"},
        headers=session["headers"],
    )
    assert client.delete(
        f"/api/sessions/{session['session_id']}", headers=session["headers"]
    ).status_code == 204
    assert client.get(
        f"/api/sessions/{session['session_id']}", headers=session["headers"]
    ).status_code == 401


def test_clearing_conversation_preserves_saved_work(client, guest_session):
    session = guest_session()
    client.post(
        "/api/turns",
        json={"text": "I need a scholarship", "language_code": "en"},
        headers=session["headers"],
    )
    saved = client.post(
        f"/api/sessions/{session['session_id']}/saved-benefits",
        json={"benefit_id": "demo-csss-cus"},
        headers=session["headers"],
    )
    assert saved.status_code == 201

    cleared = client.delete(
        f"/api/sessions/{session['session_id']}/conversation",
        headers=session["headers"],
    )
    assert cleared.status_code == 204

    body = client.get(
        f"/api/sessions/{session['session_id']}", headers=session["headers"]
    ).json()
    assert body["profile"] == {}
    assert body["conversation_state"] == {}
    assert body["turn_count"] == 0
    assert body["matched_benefit_ids"] == []
    assert client.get(
        f"/api/sessions/{session['session_id']}/transcript",
        headers=session["headers"],
    ).json() == []
    assert len(
        client.get(
            f"/api/sessions/{session['session_id']}/saved-benefits",
            headers=session["headers"],
        ).json()
    ) == 1
    assert client.get(
        f"/api/sessions/{session['session_id']}/tasks",
        headers=session["headers"],
    ).json()


def test_escalations_are_recorded_as_tickets(client, guest_session):
    session = guest_session()
    client.post(
        "/api/turns",
        json={
            "text": "I want to talk to a person",
            "language_code": "en",
        },
        headers=session["headers"],
    )
    tickets = client.get("/api/escalations").json()
    assert any(ticket["reason"] == "caller_requested" for ticket in tickets)

    ticket_id = tickets[0]["id"]
    resolved = client.post(f"/api/escalations/{ticket_id}/resolve").json()
    assert resolved["status"] == "resolved"


def test_operator_can_claim_route_note_and_resolve_escalation(client, guest_session):
    session = guest_session()
    client.post(
        "/api/turns",
        json={
            "text": "I want to talk to a person",
            "language_code": "en",
        },
        headers=session["headers"],
    )
    tickets = client.get(
        "/api/escalations?status=open&limit=100",
        headers={"X-Admin-Token": "test-admin-token"},
    ).json()
    ticket = next(item for item in tickets if item["session_id"] == session["session_id"])

    claim = client.post(
        f"/api/escalations/{ticket['id']}/claim",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert claim.status_code == 200
    assert claim.json()["status"] == "claimed"
    assert claim.json()["assigned_to"] == "local-admin"
    assert claim.json()["sla_due_at"]

    note = client.post(
        f"/api/escalations/{ticket['id']}/notes",
        json={"text": "Confirm the caller's district before referral."},
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert note.status_code == 200
    assert note.json()["operator_notes"][0]["text"].startswith("Confirm")

    routed = client.post(
        f"/api/escalations/{ticket['id']}/route",
        json={
            "department": "Karnataka district welfare desk",
            "routing_location": "Mysuru",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert routed.status_code == 200
    assert routed.json()["department"] == "Karnataka district welfare desk"
    assert routed.json()["routing_source"] == "operator_override"

    resolved = client.post(
        f"/api/escalations/{ticket['id']}/resolve",
        json={
            "resolution_code": "referred",
            "note": "Referred to the district welfare desk.",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolution_code"] == "referred"
    assert resolved.json()["resolved_by"] == "local-admin"


def test_voice_turn_reports_unavailable_rather_than_erroring(client, guest_session):
    session = guest_session()
    """With no key configured this is a deployment state, not a server fault."""
    response = client.post(
        "/api/voice/turns",
        files={"audio": ("turn.wav", b"not-real-audio", "audio/wav")},
        data={"language_code": "en"},
        headers=session["headers"],
    )
    assert response.status_code == 503


def test_empty_audio_is_rejected(client, guest_session):
    session = guest_session()
    response = client.post(
        "/api/voice/turns",
        files={"audio": ("turn.wav", b"", "audio/wav")},
        data={},
        headers=session["headers"],
    )
    assert response.status_code == 400


def test_openapi_schema_is_generated(client):
    schema = client.get("/api/openapi.json").json()
    assert "/api/turns" in schema["paths"]


def test_rag_route_fails_closed_when_hosted_store_is_not_configured(client, guest_session):
    session = guest_session()
    response = client.post(
        "/api/rag/answer",
        json={"query": "How do I apply?", "language_code": "kn"},
        headers=session["headers"],
    )
    assert response.status_code == 503


def test_voice_turn_routes_transcription_through_the_shared_rag_graph(client, guest_session):
    from sahaayak_agent import AgentRuntime, GraphDeps, Understanding
    from sahaayak_api.deps import get_runtime, get_voice
    from sahaayak_api.main import app
    from sahaayak_contracts import RagAnswerResponse, RetrievedSource, TranscriptionResult

    class FakeRetrieval:
        async def answer(self, query, *, language_code=None, **_):
            assert query == "tell me about this benefit"
            assert language_code == "kn"
            return RagAnswerResponse(
                query=query,
                answer="Kannada source answer [Source 1].",
                sources=[
                    RetrievedSource(
                        source_id="voice-source",
                        filename="voice-source.txt",
                        score=0.8,
                        excerpt="A voice source excerpt.",
                        source_url="https://example.test/voice-source",
                    )
                ],
            )

    class FakeVoice:
        tts_available = False

        async def transcribe(self, audio, *, language_code, filename):
            assert audio == b"fake-audio"
            assert language_code == "kn"
            return TranscriptionResult(
                text="tell me about this benefit",
                language_code=language_code,
                provider="fake",
            )

    app.dependency_overrides[get_runtime] = lambda: AgentRuntime(
        deps=GraphDeps(understanding=Understanding(), retrieval=FakeRetrieval())
    )
    app.dependency_overrides[get_voice] = lambda: FakeVoice()
    session = guest_session(language_code="kn")
    try:
        response = client.post(
            "/api/voice/turns",
            files={"audio": ("turn.wav", b"fake-audio", "audio/wav")},
            data={"language_code": "kn", "speak": "false"},
            headers=session["headers"],
        )
    finally:
        app.dependency_overrides.pop(get_runtime, None)
        app.dependency_overrides.pop(get_voice, None)

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "tell me about this benefit"
    assert body["response_text"] == "Kannada source answer."
    assert body["sources"][0]["source_id"] == "voice-source"
