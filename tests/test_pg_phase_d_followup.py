"""Phase D follow-up: D6 idempotent ingest + parallel-path equivalence (§8-A)."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, ingest_document, load_to_w2
from traluat.w2 import repo
from traluat.w2.db import make_engine
from traluat.w2.models import Document
from traluat.w3 import reindex_document, retrieve, retrieve_indexed

D = dt.date
FRBR = "trl:vn/nd/99/2020"
from tests.test_w1_metadata import FULL_ND  # noqa: E402
from tests.test_w1_structure import SAMPLE  # noqa: E402


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    if conn.execute(sa.text("select to_regclass('public.chunk')")).scalar() is None:
        trans.rollback(); conn.close()
        pytest.skip("chunk chưa migrate")
    s = Session(bind=conn, future=True)
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def test_d6_ingest_idempotent(session: Session):
    d1, _ = ingest_document(session, FULL_ND, "nd99")
    d2, _ = ingest_document(session, FULL_ND, "nd99")      # lần 2 cùng VB
    assert d1.id == d2.id                                   # không nhân đôi, không raise
    assert d1.source_hash and len(d1.source_hash) == 64     # sha256
    n = session.scalar(sa.select(sa.func.count()).select_from(Document)
                       .where(Document.frbr_uri == FRBR))
    assert n == 1


def _first(res, eid):
    return next((r for r in res if r.unit_eid == eid), None)


def test_parallel_path_equivalence_version_at_asof(session: Session):
    # §8-A: index phái sinh phải CHO CÙNG bản-tại-ngày như đường đọc thẳng L3.
    load_to_w2(session, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
               units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP")
    repo.apply_amendment(session, "nd99__dieu_3__khoan_2", "Mức vốn 50 tỷ đồng.",
                         D(2023, 6, 1), source_relation_id="a1")
    reindex_document(session, FRBR)                        # cập nhật L4 từ L3

    for as_of, want in [(D(2022, 1, 1), "20 tỷ"), (D(2024, 1, 1), "50 tỷ")]:
        mem = _first(retrieve(session, "mức vốn", as_of), "nd99__dieu_3__khoan_2")
        idx = _first(retrieve_indexed(session, "mức vốn", as_of), "nd99__dieu_3__khoan_2")
        assert mem is not None and idx is not None
        assert want in mem.chunk.span_text          # đường đọc thẳng L3
        assert want in idx.chunk.span_text          # L4 index — KHỚP bản-tại-ngày
