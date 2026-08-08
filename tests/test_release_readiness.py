"""Safe release-readiness projection contracts."""

from __future__ import annotations


def test_admin_system_reports_external_gates_without_secrets(client):
    response = client.get("/api/admin/system")

    assert response.status_code == 200
    body = response.json()
    assert body["release_ready"] is False
    gates = {gate["key"]: gate for gate in body["release_gates"]}
    assert {
        "production_oidc",
        "infobip",
        "ncs_api",
        "langfuse",
        "opentelemetry",
        "language_review",
        "voice_qa",
        "department_directory",
        "production_posture",
    } <= gates.keys()
    assert gates["production_oidc"]["status"] == "not_configured"
    assert gates["infobip"]["status"] == "not_configured"
    assert gates["ncs_api"]["status"] == "not_configured"
    assert "OPENAI_API_KEY" not in response.text
    assert "NCS_API_KEY" not in response.text
