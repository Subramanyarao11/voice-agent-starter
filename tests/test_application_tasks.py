"""Private document checklist and application task contracts."""

from sqlmodel import select

from sahaayak_common import ApplicationTask, EscalationTicket, SavedBenefit, UserSession, session_scope


def test_saving_a_benefit_materializes_idempotent_tasks(client, guest_session):
    session = guest_session()
    save = client.post(
        f"/api/sessions/{session['session_id']}/saved-benefits",
        json={"benefit_id": "demo-csss-cus"},
        headers=session["headers"],
    )
    assert save.status_code == 201

    first = client.get(
        f"/api/sessions/{session['session_id']}/tasks",
        headers=session["headers"],
    )
    assert first.status_code == 200
    tasks = first.json()
    assert len(tasks) >= 2
    assert {task["kind"] for task in tasks} == {"document", "application_step"}
    task_ids = {task["id"] for task in tasks}

    second = client.get(
        f"/api/sessions/{session['session_id']}/tasks?benefit_id=demo-csss-cus",
        headers=session["headers"],
    )
    assert second.status_code == 200
    assert {task["id"] for task in second.json()} == task_ids

    completed = client.post(
        f"/api/sessions/{session['session_id']}/tasks/{tasks[0]['id']}",
        json={"status": "completed"},
        headers=session["headers"],
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"]

    reopened = client.post(
        f"/api/sessions/{session['session_id']}/tasks/{tasks[0]['id']}",
        json={"status": "pending"},
        headers=session["headers"],
    )
    assert reopened.status_code == 200
    assert reopened.json()["completed_at"] is None

    removed = client.delete(
        f"/api/sessions/{session['session_id']}/saved-benefits/demo-csss-cus",
        headers=session["headers"],
    )
    assert removed.status_code == 204
    after_remove = client.get(
        f"/api/sessions/{session['session_id']}/tasks",
        headers=session["headers"],
    )
    assert after_remove.status_code == 200
    assert after_remove.json() == []


def test_tasks_are_private_to_the_owning_guest_session(client, guest_session):
    first = guest_session()
    second = guest_session()
    saved = client.post(
        f"/api/sessions/{first['session_id']}/saved-benefits",
        json={"benefit_id": "demo-csss-cus"},
        headers=first["headers"],
    )
    assert saved.status_code == 201

    response = client.get(
        f"/api/sessions/{second['session_id']}/tasks",
        headers=first["headers"],
    )
    assert response.status_code == 404


def test_reset_removes_saved_tasks_and_escalation_ticket(client, guest_session):
    session = guest_session()
    save = client.post(
        f"/api/sessions/{session['session_id']}/saved-benefits",
        json={"benefit_id": "demo-csss-cus"},
        headers=session["headers"],
    )
    assert save.status_code == 201

    with session_scope() as db:
        db.add(
            EscalationTicket(
                id=f"ticket-reset-{session['session_id']}",
                session_id=session["session_id"],
                reason="caller_requested",
            )
        )

    reset = client.delete(
        f"/api/sessions/{session['session_id']}",
        headers=session["headers"],
    )
    assert reset.status_code == 204

    with session_scope() as db:
        assert db.get(UserSession, session["session_id"]) is None
        assert db.exec(
            select(SavedBenefit).where(SavedBenefit.session_id == session["session_id"])
        ).first() is None
        assert db.exec(
            select(ApplicationTask).where(ApplicationTask.session_id == session["session_id"])
        ).first() is None
        assert db.get(EscalationTicket, f"ticket-reset-{session['session_id']}") is None
