"""End-to-end (Postgres): Celery worker body — run_task_body (test không cần broker)."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w2.db import make_engine
from traluat.w5.celery_app import register_handler, run_task_body
from traluat.w5.models import AnalysisTask


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


def test_worker_runs_handler_and_updates(session: Session):
    register_handler("ping", lambda s, p: {"pong": p.get("x", 0) + 1})
    t = AnalysisTask(tenant_id=uuid.uuid4(), kind="ping", payload={"x": 5}, status="queued")
    session.add(t); session.flush()

    assert run_task_body(session, t.id, str(t.tenant_id)) == "done"
    session.expire_all()
    done = session.get(AnalysisTask, t.id)
    assert done.result == {"pong": 6}


def test_worker_unknown_kind_errors(session: Session):
    t = AnalysisTask(tenant_id=uuid.uuid4(), kind="khong_co", payload={}, status="queued")
    session.add(t); session.flush()
    assert run_task_body(session, t.id, str(t.tenant_id)) == "error"
