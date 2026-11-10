"""End-to-end (Postgres): OCR port nối vào data-plane — ảnh → text → W2."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import (
    FullPageOCR,
    InMemorySource,
    PassthroughOCR,
    RawDocument,
    ingest_source,
)
from traluat.w2 import repo
from traluat.w2.db import make_engine

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


def test_image_only_doc_ocr_then_ingest(session: Session):
    source = InMemorySource([RawDocument(doc_slug="nd99", image_ref=b"\x89PNG-fake")])
    out = ingest_source(session, source, ocr=PassthroughOCR(FULL_ND))   # OCR trả header hợp lệ

    assert out.loaded == ["trl:vn/nd/99/2020"]
    assert "điều kiện kinh doanh" in repo.reconstruct_as_of(session, "nd99__dieu_1", D(2022, 1, 1))


def test_full_page_ocr_plugs_into_ingest(session: Session):
    # FullPageOCR (detector+recognizer) LÀ OCREngine → nạp ảnh-trang vào W2 không đụng lõi
    class _OneBand:
        def detect(self, b, lang="vi"):
            return [b]                    # 1 dải = cả trang (stub detector)

    class _Rec:
        def extract(self, b, lang="vi"):
            return FULL_ND                # recognizer trả header hợp lệ

    source = InMemorySource([RawDocument(doc_slug="nd99", image_ref=b"\x89PNG-page")])
    out = ingest_source(session, source, ocr=FullPageOCR(_OneBand(), _Rec()))
    assert out.loaded == ["trl:vn/nd/99/2020"]


def test_image_only_without_ocr_fails(session: Session):
    source = InMemorySource([RawDocument(doc_slug="x", image_ref=b"img")])
    out = ingest_source(session, source)                 # không cấu hình OCR
    assert out.loaded == [] and out.failed[0][0] == "x"
