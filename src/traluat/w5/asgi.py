"""ASGI entry — chạy `uvicorn traluat.w5.asgi:app`. Dev dùng Echo gateway (không key).

Prod: thay provider bằng ClaudeLLMGateway (local vLLM + Claude), audit PostgresAuditLog,
session per-request bind traluat_app. Đây là wiring tối thiểu để stack chạy + /metrics
scrape được.
"""

from __future__ import annotations

import os

from ..w2.db import make_session_factory
from ..w3 import EchoLLMGateway
from .api import create_app
from .metrics import Metrics
from .service import LegalService

_metrics = Metrics()
_Session = make_session_factory()


def _provider():
    s = _Session()
    try:
        yield LegalService(s, local_gateway=EchoLLMGateway(),
                           claude_gateway=EchoLLMGateway(), metrics=_metrics)
    finally:
        s.close()


def _build_neo4j():
    uri = os.environ.get("NEO4J_URI")          # vd bolt://localhost:7687
    if not uri:
        return None
    try:
        from neo4j import GraphDatabase
        drv = GraphDatabase.driver(uri, auth=(
            os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", "")))
        drv.verify_connectivity()
        return drv
    except Exception:  # noqa: BLE001 — Neo4j không bắt buộc (fallback in-degree)
        return None


app = create_app(
    jwt_secret=os.environ.get("JWT_SECRET", "dev-secret-change-me-0123456789abcd"),
    service_provider=_provider, metrics=_metrics, neo4j_driver=_build_neo4j())
