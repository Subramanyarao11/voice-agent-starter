"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sahaayak_agent.bootstrap import ensure_reference_data
from sahaayak_agent.tracing import configure_observability, shutdown_observability
from sahaayak_api.middleware import RequestContextMiddleware
from sahaayak_api.observability import (
    configure_library_instrumentation,
    shutdown_library_instrumentation,
)
from sahaayak_api.routers import (
    admin,
    browser_sessions,
    catalog,
    contact_points,
    escalations,
    health,
    rag,
    saved_benefits,
    sessions,
    telephony,
    turns,
)
from sahaayak_common import configure_logging, get_logger, init_db, settings

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_observability()
    configure_library_instrumentation()
    init_db()
    ensure_reference_data()
    log.info(
        "api_started",
        environment=settings.env,
        database="sqlite" if settings.using_sqlite else "postgres",
        speech_to_text=settings.llm_enabled,
        text_to_speech=settings.tts_enabled,
    )
    yield
    shutdown_library_instrumentation()
    shutdown_observability()


app = FastAPI(
    title="Sahaayak",
    description=(
        "Local-language voice agent for discovering government schemes, "
        "scholarships, and jobs, and checking eligibility for them."
    ),
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    # The browser demo is served from a different origin in development. In a
    # real deployment this narrows to the deployed web origin.
    allow_origins=[settings.web_base_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

app.include_router(health.router)
app.include_router(catalog.router)
app.include_router(turns.router)
app.include_router(rag.router)
app.include_router(saved_benefits.router)
app.include_router(contact_points.router)
app.include_router(browser_sessions.router)
app.include_router(sessions.router)
app.include_router(telephony.router)
app.include_router(escalations.router)
app.include_router(admin.router)
