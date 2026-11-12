"""Exercise the real ASGI provider on a non-owner login, across requests."""
import datetime as dt
import uuid

import jwt
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2.db import make_engine, make_session_factory
from traluat.w3 import EchoLLMGateway
from traluat.w5.asgi import build_runtime_app
from traluat.w5.models import (
    Alert,
    AlertSubscription,
    AnalysisTask,
    AuditLogRow,
    PlatformOperator,
    Tenant,
    TenantUser,
)
from traluat.w5.rls import set_tenant, use_app_role

SECRET = "runtime-test-private-signing-key-32-bytes-minimum"
_LOGIN = "traluat_runtime_test"
_PASSWORD = "isolated-runtime-test-only"


def _token(tid, subject, **extra):
    now = dt.datetime.now(dt.UTC)
    return jwt.encode({"iss": "traluat", "aud": "traluat-api", "sub": subject,
                       "iat": now, "exp": now + dt.timedelta(minutes=5),
                       "tenant_id": str(tid), **extra}, SECRET, algorithm="HS256")


@pytest.fixture()
def runtime():
    admin = make_engine()
    try:
        with admin.connect() as connection:
            connection.execute(sa.text("SELECT 1"))
    except sa.exc.OperationalError as exc:
        admin.dispose()
        pytest.skip(f"isolated test PostgreSQL unavailable: {exc}")
    with admin.begin() as connection:
        connection.execute(sa.text(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{_LOGIN}') "
            f"THEN CREATE ROLE {_LOGIN} LOGIN PASSWORD '{_PASSWORD}' "
            "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT; END IF; END $$"))
        connection.execute(sa.text(f"GRANT traluat_app TO {_LOGIN}"))
    a, b = uuid.uuid4(), uuid.uuid4()
    subject, other = f"user-{uuid.uuid4().hex}", f"user-{uuid.uuid4().hex}"
    with Session(admin) as session, session.begin():
        session.add_all([Tenant(id=a, slug=f"rt-{a}"), Tenant(id=b, slug=f"rt-{b}")])
        session.flush()
        session.add_all([
            TenantUser(tenant_id=a, email=f"{a}@example.invalid", auth_subject=subject, role="owner"),
            TenantUser(tenant_id=b, email=f"{b}@example.invalid", auth_subject=other, role="viewer"),
            Alert(tenant_id=a, frbr_uri="synthetic-A", change="amended", detail="private-A"),
            Alert(tenant_id=b, frbr_uri="synthetic-B", change="amended", detail="private-B"),
        ])
    runtime_engine = make_engine(admin.url.set(username=_LOGIN, password=_PASSWORD))
    sessions = make_session_factory(runtime_engine)
    app = build_runtime_app(jwt_secret=SECRET, session_factory=sessions,
                            local_gateway=EchoLLMGateway())
    client = TestClient(app, raise_server_exceptions=False)
    state = {"admin": admin, "sessions": sessions, "client": client, "a": a, "b": b,
             "subject": subject, "other": other, "app": app,
             "headers": {"Authorization": f"Bearer {_token(a, subject, role='owner')}"}}
    try:
        yield state
    finally:
        client.close()
        runtime_engine.dispose()
        with Session(admin) as session, session.begin():
            for model in (AlertSubscription, Alert, AnalysisTask, AuditLogRow, TenantUser):
                session.execute(sa.delete(model).where(model.tenant_id.in_([a, b])))
            session.execute(sa.delete(PlatformOperator).where(
                PlatformOperator.auth_subject.in_([subject, other])))
            session.execute(sa.delete(Tenant).where(Tenant.id.in_([a, b])))
        admin.dispose()


def test_real_provider_rls_and_subscription_commit(runtime):
    client, headers = runtime["client"], runtime["headers"]
    rows = client.get("/alerts", headers=headers)
    assert rows.status_code == 200
    assert [row["detail"] for row in rows.json()] == ["private-A"]
    r = client.post("/alerts/subscribe", json={"frbr": "synthetic-law"}, headers=headers)
    assert r.status_code == 200
    with Session(runtime["admin"]) as session:
        sub = session.get(AlertSubscription, r.json()["id"])
        assert sub is not None and sub.tenant_id == runtime["a"]
    # The same subject cannot select another tenant merely by changing a signed claim.
    other_tenant = {"Authorization": f"Bearer {_token(runtime['b'], runtime['subject'])}"}
    assert client.get("/alerts", headers=other_tenant).status_code == 401


def test_membership_role_change_revocation_and_suspension(runtime):
    client, headers = runtime["client"], runtime["headers"]
    assert client.post("/review", json={"text": "x"}, headers=headers).status_code == 200
    with Session(runtime["admin"]) as session, session.begin():
        session.execute(sa.update(TenantUser).where(TenantUser.tenant_id == runtime["a"])
                        .values(role="viewer"))
    assert client.post("/review", json={"text": "x"}, headers=headers).status_code == 403
    with Session(runtime["admin"]) as session, session.begin():
        session.execute(sa.update(Tenant).where(Tenant.id == runtime["a"])
                        .values(status="suspended"))
    assert client.get("/alerts", headers=headers).status_code == 401
    with Session(runtime["admin"]) as session, session.begin():
        session.execute(sa.update(Tenant).where(Tenant.id == runtime["a"]).values(status="active"))
        session.execute(sa.delete(TenantUser).where(TenantUser.tenant_id == runtime["a"]))
    assert client.get("/alerts", headers=headers).status_code == 401


def test_platform_privilege_comes_from_separate_database_identity(runtime):
    client = runtime["client"]
    spoofed = {"Authorization": f"Bearer {_token(runtime['a'], runtime['subject'], platform_operator=True)}"}
    assert client.get("/review/queue", headers=spoofed).status_code == 403
    assert client.post("/review/queue/1/approve", headers=spoofed).status_code == 403
    with Session(runtime["admin"]) as session, session.begin():
        session.add(PlatformOperator(auth_subject=runtime["subject"]))
    assert client.get("/review/queue", headers=spoofed).status_code == 200
    # A privileged identity still needs an explicitly configured write connector.
    assert client.post("/review/queue/1/approve", headers=spoofed).status_code == 503


def test_runtime_can_read_public_kb_but_cannot_mutate_audit(runtime):
    with runtime["sessions"]() as session, session.begin():
        use_app_role(session)
        set_tenant(session, str(runtime["a"]))
        assert session.scalar(sa.text("SELECT count(*) FROM document")) is not None
        session.add(AuditLogRow(tenant_id=runtime["a"], trace_id="append-only-test"))
    for statement in ("UPDATE audit_log SET action='tampered'", "DELETE FROM audit_log"):
        with runtime["sessions"]() as session, session.begin():
            use_app_role(session)
            set_tenant(session, str(runtime["a"]))
            with pytest.raises(sa.exc.ProgrammingError):
                session.execute(sa.text(statement))
            session.rollback()


def test_success_audit_persists_without_capturing_client_text(runtime):
    marker = f"synthetic-private-{uuid.uuid4().hex}"
    r = runtime["client"].post("/lookup", json={"query": marker, "as_of": "2022-01-01"},
                              headers=runtime["headers"])
    assert r.status_code == 200
    with Session(runtime["admin"]) as session:
        rows = session.scalars(sa.select(AuditLogRow).where(
            AuditLogRow.tenant_id == runtime["a"]).order_by(AuditLogRow.id)).all()
        assert [row.phase for row in rows] == ["intent", "done"]
        assert all(marker not in str(row.__dict__) for row in rows)


def test_durable_audit_survives_request_failure_before_response(runtime):
    tag = uuid.uuid4().hex
    eid = f"audit_{tag}__dieu_1"
    with Session(runtime["admin"]) as session, session.begin():
        load_to_w2(session, frbr_uri=f"synthetic:{tag}", doc_type="nghi_dinh",
                   date_effective=dt.date(2020, 1, 1),
                   units=build_ingest(f"Điều 1. Mã kiểm thử {tag} yêu cầu lưu audit.", f"audit_{tag}"))

    class FailingGateway(EchoLLMGateway):
        def generate(self, *args, **kwargs):
            # A separate connection sees the committed intent before generation.
            with Session(runtime["admin"]) as session:
                assert session.scalar(sa.select(sa.func.count()).select_from(AuditLogRow).where(
                    AuditLogRow.tenant_id == runtime["a"], AuditLogRow.phase == "intent")) == 1
            raise RuntimeError("synthetic gateway failure")

    app = build_runtime_app(jwt_secret=SECRET, session_factory=runtime["sessions"],
                            local_gateway=FailingGateway())
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post("/lookup", json={"query": tag, "as_of": "2022-01-01"},
                        headers=runtime["headers"])
        assert r.status_code == 500
    with Session(runtime["admin"]) as session:
        rows = session.scalars(sa.select(AuditLogRow).where(
            AuditLogRow.tenant_id == runtime["a"])).all()
        assert [row.phase for row in rows] == ["intent"]
        assert rows[0].actor == runtime["subject"] and rows[0].data_class == "client_sensitive"
    # Remove the synthetic KB fixture independently of request/audit cleanup.
    from traluat.w2.models import Document, Unit, UnitVersion
    with Session(runtime["admin"]) as session, session.begin():
        uid = session.scalar(sa.select(Unit.id).where(Unit.eid == eid))
        session.execute(sa.delete(UnitVersion).where(UnitVersion.unit_id == uid))
        session.execute(sa.delete(Unit).where(Unit.id == uid))
        session.execute(sa.delete(Document).where(Document.frbr_uri == f"synthetic:{tag}"))


def test_runtime_rejects_superuser_credentials(runtime):
    app = build_runtime_app(jwt_secret=SECRET,
                            session_factory=make_session_factory(runtime["admin"]))
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/alerts", headers=runtime["headers"]).status_code == 500


def test_runtime_rejects_membership_in_a_privileged_role(runtime):
    role = f"unsafe_test_{uuid.uuid4().hex}"
    with runtime["admin"].begin() as connection:
        connection.execute(sa.text(f"CREATE ROLE {role} NOLOGIN BYPASSRLS"))
        connection.execute(sa.text(f"GRANT {role} TO {_LOGIN}"))
    try:
        assert runtime["client"].get("/alerts", headers=runtime["headers"]).status_code == 500
    finally:
        with runtime["admin"].begin() as connection:
            connection.execute(sa.text(f"REVOKE {role} FROM {_LOGIN}"))
            connection.execute(sa.text(f"DROP ROLE {role}"))


def test_real_celery_wrapper_runs_and_commits(runtime, monkeypatch):
    from traluat.w2 import db
    from traluat.w5.celery_app import celery_app, register_handler

    tid = uuid.uuid4()
    kind = f"runtime_ping_{tid.hex}"
    with Session(runtime["admin"]) as session, session.begin():
        session.add(AnalysisTask(id=tid, tenant_id=runtime["a"], kind=kind,
                                 payload={"x": 5}, status="queued"))
    register_handler(kind, lambda _session, payload: {"pong": payload["x"] + 1})
    monkeypatch.setattr(db, "make_session_factory", lambda: runtime["sessions"])
    assert celery_app.run_task.run(str(tid), str(runtime["a"])) == "done"
    with Session(runtime["admin"]) as session:
        task = session.get(AnalysisTask, tid)
        assert task.status == "done" and task.result == {"pong": 6}


@pytest.mark.parametrize("kind, applied", [("repeals", True), ("amends", False)])
def test_operator_approval_applies_or_keeps_work_pending(runtime, kind, applied):
    from traluat.w2 import repo
    from traluat.w2.models import Chunk, Document, NormRelation, Unit, UnitVersion
    from traluat.w3.indexer import reindex_document
    from traluat.w3.retrieval import IndexedRetriever

    tag = uuid.uuid4().hex
    frbrs = [f"synthetic:operator:{tag}:{part}" for part in ("src", "dst")]
    with Session(runtime["admin"]) as session, session.begin():
        docs = [load_to_w2(
            session, frbr_uri=frbr, doc_type="nghi_dinh", date_effective=dt.date(2020, 1, 1),
            units=build_ingest("Điều 1. Nội dung giả dùng kiểm thử.", f"op_{tag}_{part}"),
        ) for frbr, part in zip(frbrs, ("src", "dst"))]
        target = session.scalar(sa.select(Unit).where(Unit.document_id == docs[1].id))
        eid = target.eid
        rel = NormRelation(src_doc_id=docs[0].id, dst_doc_id=docs[1].id,
                           dst_unit_id=target.id, relation_type=kind,
                           effective_date=dt.date(2021, 1, 1), review_status="needs_review")
        session.add(rel)
        session.add(PlatformOperator(auth_subject=runtime["subject"]))
        session.flush()
        rid = rel.id
        reindex_document(session, frbrs[1])
    try:
        app = build_runtime_app(jwt_secret=SECRET, session_factory=runtime["sessions"],
                                knowledge_session_factory=make_session_factory(runtime["admin"]),
                                retriever=IndexedRetriever())
        with TestClient(app) as client:
            response = client.post(f"/review/queue/{rid}/approve", headers=runtime["headers"])
            assert response.status_code == 200
            assert response.json()["materialized"] is applied
            assert response.json()["needs_materialization"] is (not applied)
            queue = client.get("/review/queue", headers=runtime["headers"]).json()
            assert any(row["id"] == rid for row in queue) is (not applied)
        with Session(runtime["admin"]) as session:
            relation = session.get(NormRelation, rid)
            assert relation.review_status == "approved"
            assert (relation.materialized_at is not None) is applied
            assert (repo.reconstruct_as_of(session, eid, dt.date(2022, 1, 1)) is None) is applied
            indexed = session.scalar(sa.select(Chunk).where(Chunk.eid == eid))
            assert indexed.valid_to == (dt.date(2021, 1, 1) if applied else None)
    finally:
        with Session(runtime["admin"]) as session, session.begin():
            dids = list(session.scalars(sa.select(Document.id).where(Document.frbr_uri.in_(frbrs))))
            uids = list(session.scalars(sa.select(Unit.id).where(Unit.document_id.in_(dids))))
            session.execute(sa.delete(NormRelation).where(NormRelation.id == rid))
            session.execute(sa.delete(Chunk).where(Chunk.unit_id.in_(uids)))
            session.execute(sa.delete(UnitVersion).where(UnitVersion.unit_id.in_(uids)))
            session.execute(sa.delete(Unit).where(Unit.id.in_(uids)))
            session.execute(sa.delete(Document).where(Document.id.in_(dids)))
