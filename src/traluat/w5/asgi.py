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


app = create_app(
    jwt_secret=os.environ.get("JWT_SECRET", "dev-secret-change-me-0123456789abcd"),
    service_provider=_provider, metrics=_metrics)
