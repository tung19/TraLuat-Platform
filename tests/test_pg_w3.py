"""End-to-end W3 slice-1 (Postgres): chunker giữ-span + retrieval keep-and-mark
+ citation gates tất định, chạy trên lõi bitemporal W2 thật."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2 import repo
from traluat.w2.bitemporal import EffectStatus
from traluat.w2.db import make_engine
from traluat.w2.models import Document, Unit, UnitVersion
from traluat.w3 import build_chunks, ground, retrieve

D = dt.date
FRBR = "trl:vn/nd/99/2020"
from tests.test_w1_structure import SAMPLE


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


def _seed(session: Session) -> None:
    load_to_w2(
        session, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
        units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP",
    )


def test_chunk_zero_drift_and_header_separation(session: Session):
    _seed(session)
    chunks = {c.unit_eid: c for c in build_chunks(session, FRBR, D(2022, 1, 1))}

    c = chunks["nd99__dieu_3__khoan_1"]
    # span_text = NGUYÊN VĂN KB@as_of (neo trích dẫn) — không lẫn header
    assert c.span_text == repo.reconstruct_as_of(session, "nd99__dieu_3__khoan_1", D(2022, 1, 1))
    assert "15 ngày" in c.span_text
    assert "99/2020/NĐ-CP" in c.struct_header and "Điều 3" in c.struct_header
    assert c.struct_header not in c.span_text                 # tách sạch
    assert c.embed_text == f"{c.struct_header}\n{c.span_text}"  # header chỉ ở embed


def test_retrieval_returns_version_at_as_of(session: Session):
    _seed(session)
    repo.apply_amendment(session, "nd99__dieu_3__khoan_2", "Mức vốn 50 tỷ đồng.",
                         D(2023, 6, 1), source_relation_id="a1")

    r22 = next(r for r in retrieve(session, "vốn", D(2022, 1, 1))
               if r.unit_eid == "nd99__dieu_3__khoan_2")
    assert "20 tỷ" in r22.chunk.span_text and r22.applicable
    assert r22.effect_status == EffectStatus.IN_FORCE

    r24 = next(r for r in retrieve(session, "vốn", D(2024, 1, 1))
               if r.unit_eid == "nd99__dieu_3__khoan_2")
    assert "50 tỷ" in r24.chunk.span_text   # giữ bản-tại-ngày, không bản cũ


def test_gate3b_blocks_wrong_number(session: Session):
    _seed(session)
    eid = "nd99__dieu_3__khoan_1"  # '… 15 ngày làm việc'

    # Preserve the source's working-day qualifier; a bare citation is not proof
    # of a paraphrase that silently drops legal conditions.
    ok = ground(session, "Doanh nghiệp phải nộp hồ sơ trong thời hạn 15 ngày làm việc.",
                D(2022, 1, 1), [eid])
    assert not ok.abstain and eid in ok.supported_eids

    bad = ground(session, "Doanh nghiệp phải nộp hồ sơ trong 30 ngày.", D(2022, 1, 1), [eid])
    assert bad.abstain and bad.reason == "no_supported_citation"
    assert bad.gates[0].gate3b_exact is False and "30 ngày" in bad.gates[0].missing_facts


def test_gate2_effectivity_and_sufficiency_floor(session: Session):
    _seed(session)
    repo.repeal(session, "nd99__dieu_5", D(2023, 6, 1))
    claim = repo.reconstruct_as_of(session, "nd99__dieu_5", D(2022, 1, 1))
    assert claim is not None

    # còn hiệu lực 2022 → qua cổng
    assert not ground(session, claim, D(2022, 1, 1), ["nd99__dieu_5"]).abstain
    # hết hiệu lực 2024 → gate2 chặn → abstain (không trích điều đã chết)
    g24 = ground(session, claim, D(2024, 1, 1), ["nd99__dieu_5"])
    assert g24.abstain and g24.gates[0].gate2_effective is False

    # R1: rỗng citation → abstain insufficient_retrieval (không bịa)
    assert ground(session, claim, D(2022, 1, 1), []).reason == "insufficient_retrieval"
    # gate1: eid không tồn tại → chặn
    assert ground(session, claim, D(2022, 1, 1), ["nd99__dieu_999"]).abstain


def test_citable_text_transitional_keeps_text(session: Session):
    # review-fix: bản chuyển tiếp đã hết covering vẫn phải TRÍCH ĐƯỢC text
    # (trước fix: đi nhánh reconstruct_as_of → None, mất nguyên văn).
    doc = Document(frbr_uri="trl:vn/l/1/2020", doc_type="luat",
                   date_effective=D(2021, 1, 1), status="con_hieu_luc")
    session.add(doc)
    session.flush()
    u = Unit(document_id=doc.id, parent_id=None, unit_type="dieu",
             ordinal=1, label="Điều 1", eid="l1__dieu_1")
    session.add(u)
    session.flush()
    session.add(UnitVersion(
        unit_id=u.id, lang="vi", valid_from=D(2021, 1, 1), valid_to=D(2023, 1, 1),
        text="Quy định cũ còn áp qua điều khoản chuyển tiếp.",
        transitional=True, status="het_hieu_luc",
    ))
    session.flush()

    text, status = repo.citable_text(session, "l1__dieu_1", D(2024, 1, 1))
    assert status == EffectStatus.TRANSITIONAL_APPLIES
    assert text == "Quy định cũ còn áp qua điều khoản chuyển tiếp."
    # keep-and-mark: trích được + áp dụng được (gate2 không chặn chuyển tiếp)
    g = ground(session, "Quy định cũ còn áp qua điều khoản chuyển tiếp.",
               D(2024, 1, 1), ["l1__dieu_1"])
    assert not g.abstain and g.gates[0].gate2_effective is True
