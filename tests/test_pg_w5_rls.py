"""End-to-end (Postgres): FORCE RLS cô lập tenant — acceptance C2, KHÔNG fail-open.

Chạy như app role NON-OWNER (traluat_app) để chứng minh policy có hiệu lực thật."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w2.db import make_engine
from traluat.w5.models import AuditLogRow
from traluat.w5.rls import set_tenant


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    if conn.execute(sa.text("select to_regclass('public.audit_log')")).scalar() is None:
        trans.rollback(); conn.close()
        pytest.skip("audit_log chưa migrate")
    s = Session(bind=conn, future=True)
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def _count(s):
    return s.scalar(sa.select(sa.func.count()).select_from(AuditLogRow))


def test_rls_isolation_no_fail_open(session: Session):
    A, B = uuid.uuid4(), uuid.uuid4()
    session.execute(sa.text("SET LOCAL ROLE traluat_app"))      # chạy như app non-owner

    set_tenant(session, str(A))
    session.add(AuditLogRow(tenant_id=A, trace_id="a", action="x")); session.flush()
    set_tenant(session, str(B))
    session.add(AuditLogRow(tenant_id=B, trace_id="b", action="y")); session.flush()

    # ★ C2: chưa SET tenant → default-deny → 0 dòng (KHÔNG fail-open thấy hết)
    session.execute(sa.text("SELECT set_config('app.current_tenant', '', true)"))
    assert _count(session) == 0

    # SET tenant A → chỉ thấy dòng của A
    set_tenant(session, str(A))
    rows = session.scalars(sa.select(AuditLogRow)).all()
    assert [r.tenant_id for r in rows] == [A]

    # SET tenant B → chỉ thấy dòng của B (không rò chéo)
    set_tenant(session, str(B))
    rows = session.scalars(sa.select(AuditLogRow)).all()
    assert [r.tenant_id for r in rows] == [B]


def test_postgres_audit_log_persists(session: Session):
    from traluat.w5 import PostgresAuditLog
    t = uuid.uuid4()
    session.execute(sa.text("SET LOCAL ROLE traluat_app"))
    set_tenant(session, str(t))
    log = PostgresAuditLog(session)
    intent = log.record_intent(
        tenant_id=str(t), actor="api", action="analyze", resource="case",
        trace_id="TR9", data_class="client_sensitive", residency="vn",
        llm_destination="local")
    log.confirm(intent, "done")
    phases = [r.phase for r in log.by_trace("TR9")]
    assert phases == ["intent", "done"]                    # write-ahead, append-only persist


def test_rls_with_check_blocks_wrong_tenant_insert(session: Session):
    A, B = uuid.uuid4(), uuid.uuid4()
    session.execute(sa.text("SET LOCAL ROLE traluat_app"))
    set_tenant(session, str(A))
    # WITH CHECK: insert dòng tenant B khi đang ở tenant A → bị chặn
    session.add(AuditLogRow(tenant_id=B, trace_id="z"))
    with pytest.raises(Exception):   # noqa: B017 — RLS violation
        session.flush()
