"""Preview or apply privacy retention windows for durable operational data.

The default is a dry run. Production scheduling should invoke this command
with ``--execute`` only after the retention values have been reviewed for the
deployment's legal and support requirements.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func
from sqlmodel import select

from sahaayak_common import (
    AuditEvent,
    ConversationTurnLog,
    EscalationTicket,
    Reminder,
    SavedBenefit,
    TelemetryEvent,
    UserSession,
    get_session,
    init_db,
    settings,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute", action="store_true", help="delete rows instead of only reporting counts"
    )
    args = parser.parse_args()
    init_db()

    now = datetime.now(UTC)
    cutoffs = {
        "transcripts": now - timedelta(days=max(1, settings.retention_transcript_days)),
        "telemetry": now - timedelta(days=max(1, settings.retention_telemetry_days)),
        "audit": now - timedelta(days=max(1, settings.retention_audit_days)),
        "escalations": now - timedelta(days=max(1, settings.retention_escalation_days)),
        "expired_sessions": now
        - timedelta(days=max(1, settings.retention_expired_session_days)),
    }

    with get_session_context() as db:
        counts = {
            "transcripts": _count_before(db, ConversationTurnLog, cutoffs["transcripts"]),
            "telemetry": _count_before(db, TelemetryEvent, cutoffs["telemetry"]),
            "audit": _count_before(db, AuditEvent, cutoffs["audit"]),
            "escalations": _count_before(db, EscalationTicket, cutoffs["escalations"]),
            "reminders": _count_before(db, Reminder, cutoffs["expired_sessions"]),
        }
        expired_sessions = db.exec(
            select(UserSession).where(
                UserSession.auth_mode == "guest",
                UserSession.expires_at.is_not(None),
                UserSession.expires_at < cutoffs["expired_sessions"],
            )
        ).all()
        counts["expired_sessions"] = len(expired_sessions)

        if args.execute:
            db.exec(
                delete(ConversationTurnLog).where(
                    ConversationTurnLog.created_at < cutoffs["transcripts"]
                )
            )
            db.exec(
                delete(TelemetryEvent).where(TelemetryEvent.created_at < cutoffs["telemetry"])
            )
            db.exec(delete(AuditEvent).where(AuditEvent.created_at < cutoffs["audit"]))
            db.exec(
                delete(EscalationTicket).where(
                    EscalationTicket.created_at < cutoffs["escalations"],
                    EscalationTicket.status != "open",
                )
            )
            db.exec(
                delete(Reminder).where(Reminder.created_at < cutoffs["expired_sessions"])
            )
            for session in expired_sessions:
                _delete_session_children(db, session.id)
                db.delete(session)
            db.commit()

    print(json.dumps({"mode": "execute" if args.execute else "dry_run", "counts": counts}))


class get_session_context:
    """Small context manager wrapper that keeps this script explicit."""

    def __enter__(self):
        self._context = get_session()
        self._session = next(self._context)
        return self._session

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self._context.close()  # type: ignore[attr-defined]
        except Exception:
            pass
        return False


def _count_before(db, model, cutoff: datetime) -> int:
    return int(
        db.exec(select(func.count()).select_from(model).where(model.created_at < cutoff)).one() or 0
    )


def _delete_session_children(db, session_id: str) -> None:
    db.exec(delete(ConversationTurnLog).where(ConversationTurnLog.session_id == session_id))
    db.exec(delete(SavedBenefit).where(SavedBenefit.session_id == session_id))
    db.exec(delete(Reminder).where(Reminder.session_id == session_id))
    db.exec(delete(EscalationTicket).where(EscalationTicket.session_id == session_id))


if __name__ == "__main__":
    main()
