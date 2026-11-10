"""FR-09 alert — theo dõi văn bản → materialize repeal → sinh Alert + deliver.

Chứng minh wiring end-to-end qua post-materialize hook (như Neo4j sync): subscribe
tenant tới 1 frbr → duyệt + materialize quan hệ repeals nhắm văn bản đó →
Alert(tenant, change='repealed') xuất hiện và đã deliver tới RecordingDeliverer.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w2 import repo
from traluat.w2.db import make_engine
from traluat.w2.models import Document, NormRelation, Unit, UnitVersion
from traluat.w5.alerts import RecordingDeliverer, enable_alert_sync, subscribe
from traluat.w5.models import Alert

D = dt.date


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    if conn.execute(sa.text("select to_regclass('public.alert')")).scalar() is None:
        trans.rollback(); conn.close()
        pytest.skip("alert chưa migrate")
    s = Session(bind=conn, future=True)
    try:
        yield s
    finally:
        repo.clear_post_materialize_hooks()
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def _doc(s: Session, frbr: str, eid: str) -> Document:
    doc = Document(frbr_uri=frbr, doc_type="nghi_dinh")
    s.add(doc); s.flush()
    s.add(Unit(document_id=doc.id, unit_type="dieu", ordinal=1, label="1", eid=eid))
    s.flush()
    s.add(UnitVersion(
        unit_id=s.scalar(sa.select(Unit.id).where(Unit.eid == eid)),
        lang="vi", valid_from=D(2021, 1, 1), valid_to=None, text=f"{eid}-gốc"))
    s.flush()
    return doc


def test_subscribe_then_repeal_fires_alert(session: Session):
    repo.clear_post_materialize_hooks()
    frbr = "trl:vn/nd/alert-1"
    doc = _doc(session, frbr, "nda1__dieu_1")
    tenant = uuid.uuid4()
    subscribe(session, tenant, frbr)

    rec = RecordingDeliverer()
    enable_alert_sync(rec)

    rel = NormRelation(
        relation_type="repeals", effective_date=D(2024, 1, 1),
        src_doc_id=doc.id, dst_doc_id=doc.id, dst_unit_id=None,
        review_status="approved")
    session.add(rel); session.flush()

    assert repo.materialize(session, rel) is True

    alerts = session.scalars(sa.select(Alert).where(Alert.tenant_id == tenant)).all()
    assert len(alerts) == 1
    assert alerts[0].change == "repealed"
    assert alerts[0].frbr_uri == frbr
    assert alerts[0].delivered is True
    assert len(rec.records) == 1


def test_no_subscriber_no_alert(session: Session):
    repo.clear_post_materialize_hooks()
    doc = _doc(session, "trl:vn/nd/alert-2", "nda2__dieu_1")
    enable_alert_sync(RecordingDeliverer())  # không ai subscribe frbr này

    rel = NormRelation(
        relation_type="repeals", effective_date=D(2024, 1, 1),
        src_doc_id=doc.id, dst_doc_id=doc.id, dst_unit_id=None,
        review_status="approved")
    session.add(rel); session.flush()
    repo.materialize(session, rel)

    assert session.scalars(
        sa.select(Alert).where(Alert.frbr_uri == "trl:vn/nd/alert-2")).all() == []


def test_non_destructive_relation_no_alert(session: Session):
    """Quan hệ cites (không huỷ/sửa) → KHÔNG sinh alert dù có subscriber."""
    repo.clear_post_materialize_hooks()
    frbr = "trl:vn/nd/alert-3"
    doc = _doc(session, frbr, "nda3__dieu_1")
    tenant = uuid.uuid4()
    subscribe(session, tenant, frbr)
    enable_alert_sync(RecordingDeliverer())

    rel = NormRelation(
        relation_type="cites", effective_date=D(2024, 1, 1),
        src_doc_id=doc.id, dst_doc_id=doc.id, dst_unit_id=None,
        review_status="approved", confidence=0.99)
    session.add(rel); session.flush()
    repo.materialize(session, rel)

    assert session.scalars(sa.select(Alert).where(Alert.tenant_id == tenant)).all() == []
