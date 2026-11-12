"""Synthetic W5 audit reproductions; no database, network, or workspace edits.

Run from the repository root:
    PYTHONPATH=src .venv/bin/python /private/tmp/traluat-audit-platform-repros.py
"""

import datetime as dt
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient

from traluat.w5.api import create_app
from traluat.w5.auth import decode_context
from traluat.w5.celery_app import celery_app
from traluat.w5.service import LegalService
from traluat.w5.tenancy import TenantContext


# This is the checked-in fallback, not a real credential.
DEFAULT_SECRET = "dev-secret-change-me-0123456789abcd"
token = jwt.encode(
    {"tenant_id": "synthetic-audit-tenant", "role": "owner"},
    DEFAULT_SECRET,
    algorithm="HS256",
)
context = decode_context(token, DEFAULT_SECRET)
assert context.tenant_id == "synthetic-audit-tenant"
assert context.role == "owner"
print("AUTH: arbitrary tenant/owner token with no expiration accepted")


class FakeService:
    def __init__(self):
        self.approved = []

    def approve_relation(self, relation_id):
        self.approved.append(relation_id)


fake_service = FakeService()
app = create_app(
    jwt_secret=DEFAULT_SECRET,
    service_provider=lambda: fake_service,
)
response = TestClient(app).post(
    "/review/queue/123/approve",
    headers={"Authorization": "Bearer " + token},
)
assert response.status_code == 200
assert fake_service.approved == [123]
print("AUTHZ: ordinary tenant owner reaches shared-KB approval method")

service = LegalService(None, local_gateway=object(), claude_gateway=object())
tenant = TenantContext("synthetic-audit-tenant")
captured = []


def fake_answer(session, query, **kwargs):
    # No gateway method is called; identity comparison only.
    captured.append((query, kwargs["gateway"] is service.claude_gateway))
    return SimpleNamespace(abstain=True, reason="synthetic-audit-mock")


private_text = "Hợp đồng SYNTHETIC-PRIVATE-CUSTOMER-123 trả lương 200 triệu"
with patch("traluat.w5.service.answer_question", fake_answer):
    service.lookup(private_text, dt.date(2026, 1, 1), tenant)
    service.summarize(private_text, dt.date(2026, 1, 1), tenant)

assert len(captured) == 2
assert all("SYNTHETIC-PRIVATE-CUSTOMER-123" in text for text, _ in captured)
assert all(selected_claude for _, selected_claude in captured)
print("EGRESS: lookup and summarize select Claude for raw synthetic private text")

assert celery_app is not None, "Celery dependency is required for this reproduction"
try:
    celery_app.run_task.run("synthetic-task-id", "synthetic-audit-tenant")
except ModuleNotFoundError as error:
    assert error.name == "traluat.w5.db", repr(error)
    print("CELERY: real task wrapper fails importing nonexistent traluat.w5.db")
else:
    raise AssertionError("Expected missing traluat.w5.db import failure")
