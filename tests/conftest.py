"""Opt-in integration DB setup. Never create, drop, or connect to the dev DB.

Set TEST_DATABASE_URL to an existing disposable database named *_test or test_*.
Its schema is migrated in place; fixtures roll their data back. Without that explicit
setting DB tests use an unreachable local URL and skip; pure tests remain available.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy.engine import make_url

_DISABLED_URL = "postgresql+psycopg://disabled:disabled@127.0.0.1:1/traluat_test?connect_timeout=1"


def _test_url() -> str | None:
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        return None
    url = make_url(value)
    name = url.database or ""
    if url.get_backend_name() != "postgresql" or not (
        name.endswith("_test") or name.startswith("test_")
    ):
        raise ValueError("TEST_DATABASE_URL must name an existing PostgreSQL *_test or test_* database")
    return value


def _migrate(url: str) -> None:
    from alembic.config import Config

    from alembic import command

    os.environ["DATABASE_URL"] = url
    command.upgrade(Config("alembic.ini"), "head")


def pytest_configure(config):
    # Install the safe value before validation/migration; failure cannot fall back to dev.
    os.environ["DATABASE_URL"] = _DISABLED_URL
    try:
        test_url = _test_url()
        if test_url:
            os.environ["DATABASE_URL"] = test_url
            _migrate(test_url)
        elif os.environ.get("REQUIRE_TEST_DATABASE") == "1":
            raise ValueError("TEST_DATABASE_URL is required for this test run")
    except Exception as exc:
        os.environ["DATABASE_URL"] = _DISABLED_URL
        raise pytest.UsageError(f"Test database setup failed: {type(exc).__name__}") from exc
