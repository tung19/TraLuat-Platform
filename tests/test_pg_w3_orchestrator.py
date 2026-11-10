"""End-to-end (Postgres): vòng grounding orchestrated với stub (Echo + HoldNLI).
Thay EchoLLMGateway→ClaudeLLMGateway là chạy thật, không đụng lõi."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2.db import make_engine
from traluat.w2.models import Document, NormRelation
from traluat.w3 import Answer, EchoLLMGateway, HoldNLI, answer_question

D = dt.date
FRBR = "trl:vn/nd/99/2020"
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


def _seed(session: Session) -> Document:
    return load_to_w2(
        session, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
        units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP",
    )


def test_full_loop_answers_with_verified_citation(session: Session):
    _seed(session)
    ans = answer_question(
        session, "vốn pháp định tối thiểu", as_of=D(2022, 1, 1),
        gateway=EchoLLMGateway(), nli=HoldNLI(),
    )
    assert not ans.abstain
    assert "nd99__dieu_3__khoan_2" in ans.citations
    assert "20 tỷ" in ans.text
    assert ans.ai_label is True and ans.confidence == 1.0
    assert ans.as_of == D(2022, 1, 1)


def test_full_loop_abstains_when_nothing_retrieved(session: Session):
    _seed(session)
    ans = answer_question(
        session, "qwxz zzzq kkkplm", as_of=D(2022, 1, 1),
        gateway=EchoLLMGateway(),
    )
    assert ans.abstain and ans.reason == "insufficient_retrieval"


def test_full_loop_caveat_on_pending_destructive_relation(session: Session):
    doc = _seed(session)
    # quan hệ 'amends' CHƯA DUYỆT nhắm nd99 → điều có thể sắp đổi → caveat (R3)
    session.add(NormRelation(
        relation_type="amends", src_doc_id=doc.id, dst_doc_id=doc.id,
        review_status="needs_review", confidence=0.75, confidence_basis="test",
    ))
    session.flush()

    ans = answer_question(
        session, "vốn pháp định tối thiểu", as_of=D(2022, 1, 1),
        gateway=EchoLLMGateway(),
    )
    assert not ans.abstain and ans.caveat is True
    assert ans.confidence <= 0.6         # trần caveat — không trả lời chắc nịch
