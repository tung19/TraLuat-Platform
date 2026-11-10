"""CN-05 · ingest bản án → ẩn danh TRƯỚC khi lưu (NQ 03/2017)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import InMemorySource, RawDocument, ingest_source
from traluat.w2 import repo
from traluat.w2.db import make_engine

D = dt.date

_BAN_AN = """\
Điều 1. Nhận định của Tòa án
Bị cáo ông Nguyễn Văn An, CMND 123456789, số điện thoại 0912345678, đã vi phạm.
"""


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


def test_judgment_anonymized_on_ingest(session: Session):
    src = InMemorySource([RawDocument(
        doc_slug="ba01", text=_BAN_AN, frbr_uri="trl:vn/ba/01", doc_type="ban_an",
        date_effective=D(2022, 1, 1), doc_number="01/2022/HS-ST")])
    out = ingest_source(session, src)
    assert out.loaded == ["trl:vn/ba/01"]

    stored = repo.reconstruct_as_of(session, "ba01__dieu_1", D(2022, 6, 1))
    assert stored is not None
    assert "Nguyễn Văn An" not in stored and "Nguyễn Văn A." in stored   # tên → viết tắt
    assert "123456789" not in stored and "[CMND]" in stored
    assert "0912345678" not in stored and "[PHONE]" in stored


def test_qppl_not_anonymized(session: Session):
    # Luật/NĐ (không phải bản án) KHÔNG bị áp ẩn danh — giữ nguyên tên cơ quan…
    txt = "Điều 1. Phạm vi\nBị cáo ông Nguyễn Văn An nêu tại Nghị định này."
    src = InMemorySource([RawDocument(
        doc_slug="nd77", text=txt, frbr_uri="trl:vn/nd/77", doc_type="nghi_dinh",
        date_effective=D(2022, 1, 1), doc_number="77/2022/NĐ-CP")])
    ingest_source(session, src)
    stored = repo.reconstruct_as_of(session, "nd77__dieu_1", D(2022, 6, 1))
    assert "Nguyễn Văn An" in stored        # QPPL không ẩn danh (không có PII thật)


def test_anonymize_can_be_disabled(session: Session):
    src = InMemorySource([RawDocument(
        doc_slug="ba02", text=_BAN_AN, frbr_uri="trl:vn/ba/02", doc_type="ban_an",
        date_effective=D(2022, 1, 1), doc_number="02/2022/HS-ST")])
    ingest_source(session, src, anonymize_judgments=False)
    stored = repo.reconstruct_as_of(session, "ba02__dieu_1", D(2022, 6, 1))
    assert "123456789" in stored            # tắt gate → giữ nguyên (chỉ cho pipeline nội bộ)
