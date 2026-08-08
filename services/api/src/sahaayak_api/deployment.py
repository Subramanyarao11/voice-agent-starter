"""Capture and compare redacted release metadata for the admin console.

The snapshot deliberately contains identifiers and capability posture only.
Secrets, source contents, transcripts, and personal data never belong in a
deployment comparison. A release is recorded on API startup and deduplicated
by a content hash, so restarting a healthy instance does not create noisy
history rows.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlmodel import Session, select

from sahaayak_common import DataImportRun, DeploymentRevision, FeatureFlag, session_scope, settings

APP_VERSION = os.getenv("SAHAAYAK_VERSION", "0.1.0")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "catalog-v1")


def record_current_deployment() -> DeploymentRevision:
    """Persist the current safe release snapshot once and return its row."""
    with session_scope() as db:
        snapshot = current_deployment_snapshot(db)
        existing = db.exec(
            select(DeploymentRevision).where(
                DeploymentRevision.release_key == snapshot["release_key"]
            )
        ).first()
        if existing is not None:
            return existing

        row = DeploymentRevision(
            id=f"deploy_{snapshot['release_key'][:32]}",
            **snapshot,
        )
        db.add(row)
        db.flush()
        return row


def current_deployment_snapshot(db: Session) -> dict[str, Any]:
    """Build a redacted, deterministic snapshot of the running release."""
    migration_revision = _migration_revision(db)
    latest_import = db.exec(
        select(DataImportRun)
        .order_by(DataImportRun.completed_at.desc())
        .limit(1)
    ).first()
    data_revision = latest_import.id if latest_import is not None else "none"

    active_flags = {
        row.key: {
            "enabled": row.enabled,
            "rollout_percentage": row.rollout_percentage,
            "target_languages": sorted(row.target_languages or []),
            "target_states": sorted(row.target_states or []),
            "revision": row.revision,
        }
        for row in db.exec(select(FeatureFlag).order_by(FeatureFlag.key)).all()
    }
    model_versions = {
        "reasoning": settings.openai_reasoning_model,
        "structuring": settings.openai_structuring_model,
        "review": settings.openai_review_model,
        "rag_answer": settings.openai_rag_answer_model,
        "transcription": settings.openai_transcription_model,
    }
    configuration = {
        "redis": bool(settings.redis_url),
        "openai": settings.llm_enabled,
        "vector_store": bool(settings.resolved_openai_vector_store_id),
        "sarvam": settings.tts_enabled,
        "langfuse": settings.tracing_enabled,
        "otel": settings.otel_enabled,
    }
    git_commit_sha = os.getenv("GIT_COMMIT_SHA", "unknown")
    image_digest = os.getenv(
        "IMAGE_DIGEST",
        os.getenv("CONTAINER_IMAGE_DIGEST", "unknown"),
    )

    release_material = {
        "environment": settings.env,
        "app_version": APP_VERSION,
        "git_commit_sha": git_commit_sha,
        "image_digest": image_digest,
        "migration_revision": migration_revision,
        "data_revision": data_revision,
        "prompt_version": PROMPT_VERSION,
        "model_versions": model_versions,
        "active_flags": active_flags,
        "configuration": configuration,
    }
    release_key = hashlib.sha256(
        json.dumps(release_material, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    return {
        "release_key": release_key,
        "environment": settings.env,
        "app_version": APP_VERSION,
        "git_commit_sha": git_commit_sha,
        "image_digest": image_digest,
        "migration_revision": migration_revision,
        "data_revision": data_revision,
        "prompt_version": PROMPT_VERSION,
        "model_versions": model_versions,
        "active_flags": active_flags,
        "configuration": configuration,
        "deployed_at": datetime.now(UTC),
    }


def _migration_revision(db: Session) -> str | None:
    try:
        value = db.exec(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
    except Exception:
        return None
    if value is None:
        return None
    try:
        return str(value[0])
    except (IndexError, KeyError, TypeError):
        return str(value)
