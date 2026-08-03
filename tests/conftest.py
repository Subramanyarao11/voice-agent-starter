"""Test configuration.

The environment is pinned before any application module is imported, because
settings are read once at import time. Tests therefore always run against a
throwaway SQLite file with no model keys and no Redis, which means the whole
dialogue suite is deterministic, offline, and free — the rule-based
understanding path exists partly so this is possible.
"""

from __future__ import annotations

import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="sahaayak-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test.db"
os.environ["REDIS_URL"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["SARVAM_API_KEY"] = ""
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""
os.environ["ADMIN_API_TOKEN"] = "test-admin-token"
os.environ["ENV"] = "test"

import pytest  # noqa: E402

from sahaayak_agent import AgentRuntime  # noqa: E402
from sahaayak_agent.bootstrap import ensure_reference_data  # noqa: E402
from sahaayak_api.rate_limit import reset_rate_limiter  # noqa: E402
from sahaayak_common import init_db, reset_cache  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    init_db()
    ensure_reference_data()


@pytest.fixture(autouse=True)
def no_real_provider_calls(monkeypatch):
    """Fail loudly if a test tries to reach Infobip for real.

    A test that configures credentials to exercise a code path can otherwise
    build the genuine adapter and dial out — which is slow, depends on the
    network, and would send real messages the moment a working key existed in
    the environment. Every provider test supplies a mock transport; anything
    without one is a bug in the test, not a reason to make a request.
    """
    from sahaayak_api.integrations.infobip.client import InfobipClient

    original = InfobipClient._get_client

    async def guarded(self):
        if self._transport is None:
            raise RuntimeError(
                "test attempted a real Infobip HTTP call; pass a mock transport "
                "or disable the channel"
            )
        return await original(self)

    monkeypatch.setattr(InfobipClient, "_get_client", guarded)


@pytest.fixture(scope="session")
def seeded(database) -> None:
    """Load the illustrative benefit set the dialogue tests reason over."""
    from datetime import date

    from sahaayak_common import Benefit, session_scope
    from scripts.seed_demo import DEMO_BENEFITS

    with session_scope() as db:
        for entry in DEMO_BENEFITS:
            db.merge(
                Benefit(
                    **entry,
                    eligibility_renewal=None,
                    last_verified_date=date.today(),
                    is_active=True,
                )
            )


@pytest.fixture
def runtime(seeded) -> AgentRuntime:
    reset_cache()
    return AgentRuntime()


@pytest.fixture
def client(seeded):
    from fastapi.testclient import TestClient

    from sahaayak_api.main import app

    reset_rate_limiter()
    with TestClient(app, headers={"X-Admin-Token": "test-admin-token"}) as test_client:
        yield test_client


@pytest.fixture
def guest_session(client):
    def create(language_code: str = "en", state_code: str = "KA") -> dict:
        response = client.post(
            "/api/browser-sessions",
            json={"language_code": language_code, "state_code": state_code},
        )
        assert response.status_code == 201
        body = response.json()
        body["headers"] = {"Authorization": f"Bearer {body['access_token']}"}
        return body

    return create


@pytest.fixture
def caller_id(request) -> str:
    """A caller unique to each test, so sessions never leak between them."""
    return f"+91{abs(hash(request.node.nodeid)) % 10_000_000_000:010d}"
