"""End-to-end W1→W2 (Postgres): parse → load → reconstruct/document_as_of."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2 import repo
from traluat.w2.db import make_engine

D = dt.date
from tests.test_w1_structure import SAMPLE  # noqa: E402


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


def test_w1_to_w2_end_to_end(session: Session):
    units = build_ingest(SAMPLE, "nd99")
    load_to_w2(
        session, frbr_uri="trl:vn/nd/99/2020", doc_type="nghi_dinh",
        date_effective=D(2021, 1, 1), units=units, doc_number="99/2020/NĐ-CP",
    )

    # moat #1 chạy trên dữ liệu PARSE THẬT
    assert repo.reconstruct_as_of(session, "nd99__dieu_3__khoan_1", D(2020, 1, 1)) is None  # chưa hiệu lực
    assert "15 ngày" in repo.reconstruct_as_of(session, "nd99__dieu_3__khoan_1", D(2022, 1, 1))
    assert "20 tỷ" in repo.reconstruct_as_of(session, "nd99__dieu_3__khoan_2", D(2022, 1, 1))

    # ghép cả văn bản theo cây
    doc = repo.document_as_of(session, "trl:vn/nd/99/2020", D(2022, 1, 1))
    assert "Chương I" in doc and "Chương II" in doc
    assert "Điều 5" in doc and doc.index("Chương I") < doc.index("Chương II")


def test_w1_then_amend_materialize(session: Session):
    units = build_ingest(SAMPLE, "nd99")
    load_to_w2(session, frbr_uri="trl:vn/nd/99/2020", doc_type="nghi_dinh",
               date_effective=D(2021, 1, 1), units=units)
    # sửa đổi Khoản 2 (vốn 20→50 tỷ) hiệu lực 2023
    repo.apply_amendment(session, "nd99__dieu_3__khoan_2", "Mức vốn 50 tỷ đồng.",
                         D(2023, 6, 1), source_relation_id="amend1")
    assert "20 tỷ" in repo.reconstruct_as_of(session, "nd99__dieu_3__khoan_2", D(2022, 1, 1))
    assert repo.reconstruct_as_of(session, "nd99__dieu_3__khoan_2", D(2024, 1, 1)) == "Mức vốn 50 tỷ đồng."
