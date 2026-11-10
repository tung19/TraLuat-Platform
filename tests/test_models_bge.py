"""Model THẬT bge-m3 — Embedder port + dense retrieval. @slow (tải ~2.3GB lần đầu).

Skip nếu chưa cài extra 'models' (sentence-transformers)."""

from __future__ import annotations

import datetime as dt

import pytest

pytest.importorskip("sentence_transformers")

from sqlalchemy.orm import Session  # noqa: E402

from traluat.w1 import build_ingest, load_to_w2  # noqa: E402
from traluat.w2.db import make_engine  # noqa: E402
from traluat.w3 import retrieve  # noqa: E402
from traluat.w3.embed_bge import BgeM3Embedder  # noqa: E402

D = dt.date
FRBR = "trl:vn/nd/99/2020"
from tests.test_w1_structure import SAMPLE  # noqa: E402


@pytest.fixture(scope="module")
def embedder():
    return BgeM3Embedder()


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_embed_dim_and_semantics(embedder):
    v = embedder.embed(["vốn pháp định tối thiểu",
                        "mức vốn điều lệ ban đầu của công ty",
                        "thủ tục ly hôn"])
    assert len(v) == 3 and len(v[0]) == 1024 == embedder.dim
    assert _cos(v[0], v[1]) > _cos(v[0], v[2])      # gần ngữ nghĩa > xa


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    s = Session(bind=conn, future=True)
    load_to_w2(s, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
               units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP")
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def test_dense_finds_what_lexical_misses(session: Session, embedder):
    # query KHÔNG trùng từ khóa với 'Mức vốn pháp định tối thiểu là 20 tỷ đồng'
    q = "cần bao nhiêu tiền để thành lập công ty"
    lex = retrieve(session, q, D(2022, 1, 1))                       # lexical
    dense = retrieve(session, q, D(2022, 1, 1), embedder=embedder)  # dense

    lex_eids = {r.unit_eid for r in lex}
    dense_top = [r.unit_eid for r in dense[:3]]
    assert "nd99__dieu_3__khoan_2" not in lex_eids      # lexical bỏ lỡ (0 overlap)
    assert "nd99__dieu_3__khoan_2" in dense_top         # dense bắt được (ngữ nghĩa)
