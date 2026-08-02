import uuid

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.db import get_session
from app.models.core import UserSession

router = APIRouter()


@router.post("/")
def create_session(
    phone_or_session_id: str,
    state_code: str,
    language_code: str,
    db: Session = Depends(get_session),
):
    existing = db.exec(
        select(UserSession).where(UserSession.phone_or_session_id == phone_or_session_id)
    ).first()
    if existing:
        return existing  # long-running: same caller resumes their session

    session = UserSession(
        id=str(uuid.uuid4()),
        phone_or_session_id=phone_or_session_id,
        state_code=state_code,
        language_code=language_code,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}")
def get_session_by_id(session_id: str, db: Session = Depends(get_session)):
    return db.get(UserSession, session_id)
