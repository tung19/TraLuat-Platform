"""Engine/session factory. DATABASE_URL hoặc default dev (docker-compose, port 5433)."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DEFAULT_URL = "postgresql+psycopg://traluat:traluat@localhost:5433/traluat"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def make_engine(url: str | None = None):
    return create_engine(url or database_url(), future=True)


def make_session_factory(engine=None):
    return sessionmaker(bind=engine or make_engine(), future=True)
