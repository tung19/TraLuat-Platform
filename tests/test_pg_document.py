"""Integration (Postgres) — document_as_of: ghép CẢ VĂN BẢN theo cây (M4-fix)."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w2 import repo
from traluat.w2.db import make_engine
from traluat.w2.models import Document, Unit, UnitVersion

D = dt.date
FRBR = "trl:vn/nd/doc"


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
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


def _hierarchical_doc(s: Session) -> None:
    """Chương I > (Điều 1, Điều 2) · Chương II > Điều 3. (chèn lệch ordinal để test sort)"""
    doc = Document(frbr_uri=FRBR, doc_type="nghi_dinh")
    s.add(doc); s.flush()

    ch1 = Unit(document_id=doc.id, parent_id=None, unit_type="chuong", ordinal=1,
               label="Chương I", eid="d__chuong_1")
    ch2 = Unit(document_id=doc.id, parent_id=None, unit_type="chuong", ordinal=2,
               label="Chương II", eid="d__chuong_2")
    s.add_all([ch1, ch2]); s.flush()

    # cố ý thêm Điều 2 TRƯỚC Điều 1 → document_as_of phải sort theo ordinal
    d2 = Unit(document_id=doc.id, parent_id=ch1.id, unit_type="dieu", ordinal=2,
              label="Điều 2", eid="d__dieu_2")
    d1 = Unit(document_id=doc.id, parent_id=ch1.id, unit_type="dieu", ordinal=1,
              label="Điều 1", eid="d__dieu_1")
    d3 = Unit(document_id=doc.id, parent_id=ch2.id, unit_type="dieu", ordinal=1,
              label="Điều 3", eid="d__dieu_3")
    s.add_all([d2, d1, d3]); s.flush()

    for eid, txt in [("d__dieu_1", "nội dung 1"), ("d__dieu_2", "nội dung 2"),
                     ("d__dieu_3", "nội dung 3")]:
        s.add(UnitVersion(
            unit_id=s.scalar(sa.select(Unit.id).where(Unit.eid == eid)),
            lang="vi", valid_from=D(2021, 1, 1), valid_to=None, text=txt))
    s.flush()


def test_document_as_of_tree(session: Session):
    _hierarchical_doc(session)
    out = repo.document_as_of(session, FRBR, D(2022, 1, 1))
    lines = out.splitlines()

    # tiêu đề Chương (kết cấu, không text) + nội dung Điều, đúng thứ tự cây
    assert lines == [
        "Chương I",
        "  Điều 1. nội dung 1",     # ordinal 1 trước 2 (dù chèn ngược)
        "  Điều 2. nội dung 2",
        "Chương II",
        "  Điều 3. nội dung 3",
    ]


def test_document_as_of_omits_repealed(session: Session):
    _hierarchical_doc(session)
    repo.repeal(session, "d__dieu_2", D(2024, 1, 1), source_relation_id="rp2")

    out = repo.document_as_of(session, FRBR, D(2025, 1, 1))
    assert "Điều 2" not in out                    # đã bãi bỏ → bỏ
    assert "Điều 1. nội dung 1" in out            # còn
    assert "Điều 3. nội dung 3" in out
    # nhưng "văn bản tại ngày 2023" vẫn còn Điều 2 (bitemporal)
    assert "Điều 2. nội dung 2" in repo.document_as_of(session, FRBR, D(2023, 1, 1))
