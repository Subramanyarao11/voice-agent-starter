"""Citizen-confirmed Saathi actions mutate only their real downstream records."""

from datetime import UTC, datetime

from sqlmodel import select

from sahaayak_common import (
    ApplicationCase,
    ApplicationStatusEvent,
    ApplicationTask,
    AssistanceSession,
    Benefit,
    EscalationTicket,
    UserSession,
    session_scope,
)
from sahaayak_contracts import VerificationStatus


def _citizen(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _prepare_session(client, *, token: str, purpose: str) -> dict:
    citizen_headers = _citizen(token)
    invitation = client.post(
        "/api/assistance/invitations",
        headers=citizen_headers,
        json={"purpose": purpose},
    )
    assert invitation.status_code == 201, invitation.text
    body = invitation.json()
    redeemed = client.post(
        "/api/assistant/invitations/redeem",
        json={"invitation_token": body["invitation_token"]},
    )
    assert redeemed.status_code == 200, redeemed.text
    consented = client.post(
        f"/api/assistance/invitations/{body['id']}/consent",
        headers=citizen_headers,
        json={"confirm": True},
    )
    assert consented.status_code == 200, consented.text
    return {"id": body["id"], "citizen": citizen_headers}


def test_confirmed_application_reference_updates_application_case(client) -> None:
    session = _prepare_session(
        client,
        token="test-citizen-assistance-application",
        purpose="record_application_reference",
    )
    with session_scope() as db:
        assistance = db.get(AssistanceSession, session["id"])
        assert assistance is not None
        assert assistance.citizen_session_id is not None
        account_session = db.get(UserSession, assistance.citizen_session_id)
        assert account_session is not None
        benefit = db.get(Benefit, "demo-csss-cus")
        assert benefit is not None
        case = ApplicationCase(
            id="assisted-case-application",
            session_id=account_session.id,
            citizen_account_id=assistance.citizen_account_id,
            benefit_id=benefit.id,
            benefit_snapshot={
                "name": benefit.name,
                "source_document_url": benefit.source_document_url or benefit.source_url,
            },
            status="draft",
            status_recorded_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(case)

    draft = client.post(
        f"/api/assistant/sessions/{session['id']}/draft-actions",
        json={
            "action_key": "record_application_reference",
            "target_type": "application_case",
            "target_id": "assisted-case-application",
            "application_status": "submitted",
            "external_reference": "NSP-2026-42",
            "preview_code": "application_reference_review",
            "idempotency_key": "assisted-application-001",
        },
    )
    assert draft.status_code == 201, draft.text
    assert draft.json()["effect_reference_masked"] == ""

    confirmed = client.post(
        f"/api/assistance/sessions/{session['id']}/actions/{draft.json()['id']}/confirm",
        headers=session["citizen"],
        json={"confirm": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    executed = client.post(
        f"/api/assistant/sessions/{session['id']}/actions/{draft.json()['id']}/execute"
    )
    assert executed.status_code == 200, executed.text
    result = executed.json()
    assert result["effect_code"] == "application_status_recorded"
    assert result["effect_record_id"] == "assisted-case-application"
    assert result["effect_reference_masked"] == "••••42"

    with session_scope() as db:
        case = db.get(ApplicationCase, "assisted-case-application")
        assert case is not None
        assert case.status == "submitted"
        assert case.external_reference_masked == "••••42"
        assert case.external_reference_ciphertext
        assert "NSP-2026-42" not in case.external_reference_ciphertext
        events = db.exec(
            select(ApplicationStatusEvent).where(
                ApplicationStatusEvent.application_case_id == case.id
            )
        ).all()
        assert events[-1].actor_type == "operator"


def test_prepare_application_creates_real_case_and_checklist(client) -> None:
    session = _prepare_session(
        client,
        token="test-citizen-assistance-prepare",
        purpose="prepare_application",
    )
    with session_scope() as db:
        benefit = db.get(Benefit, "demo-csss-cus")
        assert benefit is not None
        benefit.verification_status = VerificationStatus.HUMAN_VERIFIED
        benefit.is_active = True
        db.add(benefit)

    draft = client.post(
        f"/api/assistant/sessions/{session['id']}/draft-actions",
        json={
            "action_key": "prepare_application",
            "target_type": "benefit",
            "target_id": "demo-csss-cus",
            "preview_code": "prepare_application_review",
            "idempotency_key": "assisted-prepare-001",
        },
    )
    assert draft.status_code == 201, draft.text
    action_id = draft.json()["id"]
    assert client.post(
        f"/api/assistance/sessions/{session['id']}/actions/{action_id}/confirm",
        headers=session["citizen"],
        json={"confirm": True},
    ).status_code == 200
    executed = client.post(
        f"/api/assistant/sessions/{session['id']}/actions/{action_id}/execute"
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["effect_code"] == "application_case_prepared"

    with session_scope() as db:
        assistance = db.get(AssistanceSession, session["id"])
        assert assistance is not None
        case = db.exec(
            select(ApplicationCase).where(
                ApplicationCase.session_id == assistance.citizen_session_id,
                ApplicationCase.benefit_id == "demo-csss-cus",
            )
        ).one()
        tasks = db.exec(
            select(ApplicationTask).where(ApplicationTask.application_case_id == case.id)
        ).all()
        assert case.application_channel == "assisted"
        assert case.status == "draft"
        assert tasks


def test_confirmed_department_action_creates_operator_queue_ticket(client) -> None:
    session = _prepare_session(
        client,
        token="test-citizen-assistance-escalation",
        purpose="create_escalation",
    )
    draft = client.post(
        f"/api/assistant/sessions/{session['id']}/draft-actions",
        json={
            "action_key": "create_escalation",
            "target_type": "department",
            "target_id": "",
            "preview_code": "human_support_review",
            "idempotency_key": "assisted-escalation-001",
        },
    )
    assert draft.status_code == 201, draft.text
    action_id = draft.json()["id"]
    assert client.post(
        f"/api/assistance/sessions/{session['id']}/actions/{action_id}/confirm",
        headers=session["citizen"],
        json={"confirm": True},
    ).status_code == 200
    executed = client.post(
        f"/api/assistant/sessions/{session['id']}/actions/{action_id}/execute"
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["effect_code"] == "escalation_ticket_created"

    with session_scope() as db:
        ticket = db.exec(
            select(EscalationTicket).where(
                EscalationTicket.reason == "assisted_saathi:create_escalation"
            )
        ).first()
        assert ticket is not None
        assert ticket.status == "open"
        assert ticket.routing_source == "state_domain_fallback"
