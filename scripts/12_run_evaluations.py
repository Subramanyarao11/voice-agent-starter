"""Run deterministic conversation regression cases without provider calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlmodel import select

from sahaayak_agent import AgentRuntime, GraphDeps
from sahaayak_agent.bootstrap import ensure_reference_data
from sahaayak_agent.understanding import Understanding
from sahaayak_common import (
    REPO_ROOT,
    Benefit,
    ConversationTurnLog,
    EscalationTicket,
    EvaluationRun,
    Reminder,
    SavedBenefit,
    UserSession,
    init_db,
    session_scope,
)
from sahaayak_contracts import VerificationStatus


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", dest="case_ids", help="run only this case ID")
    parser.add_argument(
        "--seed-demo",
        action="store_true",
        help="load the illustrative demo rows when running against an empty local database",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep evaluation sessions for debugging instead of cleaning them up",
    )
    args = parser.parse_args()
    init_db()
    ensure_reference_data()
    if args.seed_demo:
        _seed_demo_rows()

    suite_path = REPO_ROOT / "evals" / "conversations.json"
    suite_bytes = suite_path.read_bytes()
    cases = json.loads(suite_bytes)
    selected = [case for case in cases if not args.case_ids or case["id"] in args.case_ids]
    runtime = AgentRuntime(deps=GraphDeps(understanding=Understanding()))
    run_id = uuid.uuid4().hex[:12]
    started_at = datetime.now(UTC)
    results = [_run_case(runtime, case, run_id, keep=args.keep) for case in selected]
    payload = {"passed": all(result["passed"] for result in results), "cases": results}
    completed_at = datetime.now(UTC)
    language_counts: dict[str, int] = {}
    for case in selected:
        language = str(case.get("language") or "unknown")
        language_counts[language] = language_counts.get(language, 0) + 1
    with session_scope() as db:
        db.add(
            EvaluationRun(
                id=f"eval_{run_id}",
                suite_name="conversation-regression",
                suite_version=hashlib.sha256(suite_bytes).hexdigest()[:16],
                passed=bool(payload["passed"]),
                case_count=len(results),
                passed_count=sum(bool(result["passed"]) for result in results),
                failed_count=sum(not bool(result["passed"]) for result in results),
                language_counts=language_counts,
                report_json=payload,
                started_at=started_at,
                completed_at=completed_at,
            )
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not payload["passed"]:
        raise SystemExit(1)


def _run_case(runtime: AgentRuntime, case: dict, run_id: str, *, keep: bool) -> dict:
    import asyncio

    async def run():
        state = None
        for turn in case["turns"]:
            _, state = await runtime.run_turn(
                caller_id=f"eval:{run_id}:{case['id']}",
                transcript=turn,
                language_code=case["language"],
                state_code=case["state"],
            )
        expected = case["expect"]
        match_ids = [match.benefit_id for match in (state.matches if state else [])]
        passed = bool(state and state.response_text)
        if expected.get("response") is False:
            passed = passed is False
        if "match_id" in expected:
            passed = passed and expected["match_id"] in match_ids
        if "escalated" in expected:
            passed = passed and bool(state and state.needs_escalation) is expected["escalated"]
        return {
            "id": case["id"],
            "passed": passed,
            "session_id": state.session_id if state else None,
            "turns": len(case["turns"]),
            "match_ids": match_ids,
            "pending_slot": state.pending_slot.value if state and state.pending_slot else None,
            "escalated": bool(state and state.needs_escalation),
        }

    result = asyncio.run(run())
    if not keep:
        _delete_session(result.get("session_id"))
        result.pop("session_id", None)
    return result


def _delete_session(session_id: str | None) -> None:
    if not session_id:
        return
    with session_scope() as db:
        row = db.get(UserSession, session_id)
        if row is None:
            return
        for model in (ConversationTurnLog, SavedBenefit, Reminder, EscalationTicket):
            for child in db.exec(select(model).where(model.session_id == session_id)).all():
                db.delete(child)
        db.delete(row)


def _seed_demo_rows() -> None:
    from datetime import date

    from scripts.seed_demo import DEMO_BENEFITS

    with session_scope() as db:
        for entry in DEMO_BENEFITS:
            db.merge(
                Benefit(
                    **entry,
                    eligibility_renewal=None,
                    last_verified_date=date.today(),
                    verification_status=VerificationStatus.ILLUSTRATIVE,
                    source_title="myScheme reference (illustrative demo)",
                    source_document_url=entry.get("source_url", ""),
                    is_active=True,
                )
            )


if __name__ == "__main__":
    main()
