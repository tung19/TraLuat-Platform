"""End-to-end (Postgres): ingest_source — nạp cả mẻ từ DocumentSource, lỗi 1 VB
không chặn mẻ."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import InMemorySource, RawDocument, ingest_source
from traluat.w2 import repo
from traluat.w2.db import make_engine

import datetime as dt

D = dt.date
from tests.test_w1_metadata import FULL_ND  # noqa: E402


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


def test_ingest_source_batch_isolates_failures(session: Session):
    source = InMemorySource([
        RawDocument(doc_slug="nd99", text=FULL_ND),                 # đủ metadata → nạp
        RawDocument(doc_slug="bad", text="Điều 1. Thiếu header."),  # thiếu 'Số:' → fail
    ])
    out = ingest_source(session, source)

    assert out.loaded == ["trl:vn/nd/99/2020"]
    assert len(out.failed) == 1 and out.failed[0][0] == "bad"
    # VB tốt đã vào kho, chạy được bitemporal; VB lỗi bị cô lập
    assert "điều kiện kinh doanh" in repo.reconstruct_as_of(session, "nd99__dieu_1", D(2022, 1, 1))
