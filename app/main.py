import structlog
from fastapi import FastAPI

from app.core.db import init_db
from app.routers import session, voice

log = structlog.get_logger()

app = FastAPI(title="Local-Language Voice Utility Agent")


@app.on_event("startup")
def on_startup():
    init_db()
    log.info("startup_complete")


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(session.router, prefix="/sessions", tags=["sessions"])
app.include_router(voice.router, prefix="/voice", tags=["voice"])
