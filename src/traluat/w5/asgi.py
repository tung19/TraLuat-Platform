"""Uvicorn factory: traluat.w5.asgi:app_from_env --factory.

Validated auth, scoped transactions, local AI and durable metadata-only audit.
"""

from __future__ import annotations

import os

from ..w2.db import make_engine, make_session_factory
from ..w3.local_gateway import DisabledLLMGateway
from .ai_runtime import load_runtime_ai
from .api import create_app
from .audit import DurablePostgresAuditLog
from .auth import DEFAULT_AUDIENCE, DEFAULT_ISSUER
from .metrics import Metrics
from .rls import ensure_runtime_login, use_app_role
from .service import LegalService


def build_runtime_app(
    *, jwt_secret: str, session_factory=None, local_gateway=None,
    claude_gateway=None, knowledge_session_factory=None,
    jwt_issuer: str = DEFAULT_ISSUER, jwt_audience: str = DEFAULT_AUDIENCE,
    retriever=None, nli=None,
):
    sessions = session_factory or make_session_factory()
    metrics = Metrics()
    local = local_gateway if local_gateway is not None else DisabledLLMGateway()

    def provider():
        with sessions() as session:
            try:
                ensure_runtime_login(session)
                use_app_role(session)
                yield LegalService(
                    session, local_gateway=local, claude_gateway=claude_gateway,
                    audit=DurablePostgresAuditLog(sessions), metrics=metrics,
                    knowledge_session_factory=knowledge_session_factory,
                    retriever=retriever, nli=nli,
                )
                session.commit()
            except Exception:
                session.rollback()
                raise

    return create_app(
        jwt_secret=jwt_secret, jwt_issuer=jwt_issuer, jwt_audience=jwt_audience,
        service_provider=provider, metrics=metrics, neo4j_driver=_build_neo4j(),
    )


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


def app_from_env():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL must name a non-owner runtime login")
    knowledge_url = os.environ.get("KNOWLEDGE_DATABASE_URL")
    knowledge_sessions = (make_session_factory(make_engine(knowledge_url))
                          if knowledge_url else None)
    from .auth import validate_secret
    validate_secret(os.environ.get("JWT_SECRET", ""))
    ai = load_runtime_ai()
    return build_runtime_app(
        jwt_secret=os.environ.get("JWT_SECRET", ""),
        session_factory=make_session_factory(make_engine(database_url)),
        jwt_issuer=os.environ.get("JWT_ISSUER", DEFAULT_ISSUER),
        jwt_audience=os.environ.get("JWT_AUDIENCE", DEFAULT_AUDIENCE),
        knowledge_session_factory=knowledge_sessions,
        local_gateway=ai.gateway, retriever=ai.retriever, nli=ai.nli,
    )
