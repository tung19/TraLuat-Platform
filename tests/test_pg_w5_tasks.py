"""End-to-end (Postgres): async TaskRunner + RLS task-ownership (IDOR C6)."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w2.db import make_engine
from traluat.w5 import TaskRunner
from traluat.w5.tenancy import TenantContext


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    if conn.execute(sa.text("select to_regclass('public.analysis_task')")).scalar() is None:
        trans.rollback(); conn.close()
        pytest.skip("analysis_task chưa migrate")
    s = Session(bind=conn, future=True)
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def test_task_runs_eager_and_idor_protected(session: Session):
    A, B = str(uuid.uuid4()), str(uuid.uuid4())
    ctxA = TenantContext(A, role="lawyer")
    ctxB = TenantContext(B, role="lawyer")
    runner = TaskRunner(session)                       # InMemory eager

    tid = runner.submit(ctxA, "analyze", lambda: {"ok": True, "n": 1})

    got = runner.get(ctxA, tid)                         # chủ sở hữu → thấy, done
    assert got is not None and got.status == "done" and got.result == {"ok": True, "n": 1}

    # ★ C6 IDOR: tenant B fetch task của A → RLS trả None (không rò)
    assert runner.get(ctxB, tid) is None


def test_task_error_captured(session: Session):
    A = str(uuid.uuid4())
    ctxA = TenantContext(A, role="lawyer")
    runner = TaskRunner(session)

    def boom():
        raise RuntimeError("hỏng")

    tid = runner.submit(ctxA, "analyze", boom)
    got = runner.get(ctxA, tid)
    assert got.status == "error" and "hỏng" in got.error
