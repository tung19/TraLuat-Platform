"""Integration (Postgres) slice-3 — materialize GATE + doc-level repeal + out-of-order."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w2 import repo
from traluat.w2.db import make_engine
from traluat.w2.models import Document, NormRelation, Unit, UnitVersion

D = dt.date


@pytest.fixture()
def session():
    try:
        engine = make_engine()
        conn = engine.connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    s = Session(bind=conn, future=True)
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def _doc_with_units(s: Session, frbr: str, eids: list[str]) -> Document:
    doc = Document(frbr_uri=frbr, doc_type="nghi_dinh")
    s.add(doc)
    s.flush()
    for i, eid in enumerate(eids, 1):
        s.add(Unit(document_id=doc.id, unit_type="dieu", ordinal=i, label=str(i), eid=eid))
    s.flush()
    for eid in eids:
        s.add(UnitVersion(
            unit_id=s.scalar(sa.select(Unit.id).where(Unit.eid == eid)),
            lang="vi", valid_from=D(2021, 1, 1), valid_to=None, text=f"{eid}-gốc",
        ))
    s.flush()
    return doc


def test_materialize_gate_blocks_unapproved_repeal(session: Session):
    doc = _doc_with_units(session, "trl:vn/nd/1", ["nd1__dieu_1"])
    rel = NormRelation(
        relation_type="repeals", effective_date=D(2024, 1, 1),
        src_doc_id=doc.id, dst_doc_id=doc.id, dst_unit_id=None,
        review_status="needs_review", confidence=0.99,  # confidence cao vẫn KHÔNG auto repeal
    )
    session.add(rel); session.flush()

    assert repo.materialize(session, rel) is False          # bị chặn
    # chưa bị tombstone → vẫn đọc được tại 2025
    assert repo.reconstruct_as_of(session, "nd1__dieu_1", D(2025, 1, 1)) == "nd1__dieu_1-gốc"


def test_materialize_approved_doc_level_repeal(session: Session):
    doc = _doc_with_units(session, "trl:vn/nd/2", ["nd2__dieu_1", "nd2__dieu_2"])
    rel = NormRelation(
        relation_type="repeals", effective_date=D(2024, 1, 1),
        src_doc_id=doc.id, dst_doc_id=doc.id, dst_unit_id=None,  # doc-level
        review_status="approved",
    )
    session.add(rel); session.flush()

    assert repo.materialize(session, rel) is True
    # ★ G3-fix: CẢ 2 điều của văn bản đều bị tombstone từ 2024
    for eid in ("nd2__dieu_1", "nd2__dieu_2"):
        assert repo.reconstruct_as_of(session, eid, D(2023, 1, 1)) == f"{eid}-gốc"
        assert repo.reconstruct_as_of(session, eid, D(2024, 6, 1)) is None


def test_out_of_order_split_via_db(session: Session):
    _doc_with_units(session, "trl:vn/nd/3", ["nd3__dieu_1"])
    eid = "nd3__dieu_1"
    repo.apply_amendment(session, eid, "C", D(2025, 1, 1), source_relation_id="r25")
    repo.apply_amendment(session, eid, "B", D(2023, 1, 1), source_relation_id="r23")  # lệch thứ tự
    assert repo.reconstruct_as_of(session, eid, D(2022, 1, 1)) == "nd3__dieu_1-gốc"
    assert repo.reconstruct_as_of(session, eid, D(2024, 1, 1)) == "B"
    assert repo.reconstruct_as_of(session, eid, D(2026, 1, 1)) == "C"
