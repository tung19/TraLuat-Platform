"""End-to-end (Postgres): ingest_document — không truyền tay doc_number/
date_effective/frbr_uri; metadata tự trích rồi nạp vào W2."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import ingest_document
from traluat.w2 import repo
from traluat.w2.db import make_engine
from traluat.w2.models import Document

D = dt.date
from tests.test_w1_metadata import FULL_ND


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


def test_ingest_document_no_manual_args(session: Session):
    doc, _meta = ingest_document(session, FULL_ND, "nd99")

    assert doc.frbr_uri == "trl:vn/nd/99/2020"       # suy từ metadata
    assert doc.doc_type == "nghi_dinh"
    assert doc.date_effective == D(2021, 1, 1)
    assert doc.date_issued == D(2020, 6, 15)
    assert doc.authority_id is not None              # Authority 'CHÍNH PHỦ' đã tạo/resolve

    # bitemporal chạy đúng theo date_effective TỰ TRÍCH
    assert repo.reconstruct_as_of(session, "nd99__dieu_1", D(2020, 1, 1)) is None   # chưa hiệu lực
    assert "điều kiện kinh doanh" in repo.reconstruct_as_of(session, "nd99__dieu_1", D(2022, 1, 1))


def test_ingest_document_missing_metadata_raises(session: Session):
    # không có 'Số:' → không suy được frbr_uri/doc_type → từ chối, không ingest nửa vời
    with pytest.raises(ValueError, match="frbr_uri"):
        ingest_document(session, "Điều 1. Nội dung nào đó.", "x")
    assert session.scalar(Document.__table__.select()) is None
