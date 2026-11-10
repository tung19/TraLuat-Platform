"""End-to-end (Postgres): ReasoningEngine một-lượt Researcher→Auditor→Adjudicator."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2.bitemporal import EffectStatus
from traluat.w2.db import make_engine
from traluat.w3 import Citation, EchoLLMGateway
from traluat.w3.gateway import BaseLLMGateway
from traluat.w4 import CaseInput, ReasoningEngine

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


def _seed(session: Session) -> None:
    load_to_w2(session, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
               units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP")


def test_single_mode_adjudicates_on_verified(session: Session):
    _seed(session)
    eng = ReasoningEngine(session, gateway=EchoLLMGateway())
    adj = eng.analyze(CaseInput(facts="vốn pháp định tối thiểu của doanh nghiệp"),
                      as_of=D(2022, 1, 1))

    (party,) = adj.parties
    assert not party.abstain
    assert "nd99__dieu_3__khoan_2" in party.citations
    assert party.effect_status["nd99__dieu_3__khoan_2"] == EffectStatus.IN_FORCE
    assert adj.verified_articles and adj.draft and adj.ai_label is True
    assert adj.verified_precedents == []


def test_h1_abstain_when_no_basis(session: Session):
    _seed(session)
    eng = ReasoningEngine(session, gateway=EchoLLMGateway())
    adj = eng.analyze(CaseInput(facts="qwxz zzzq kkkplm"), as_of=D(2022, 1, 1))

    (party,) = adj.parties
    assert party.abstain and party.reason == "insufficient_basis"
    assert adj.verified_articles == []


def test_element_gate_narrows_candidates(session: Session):
    _seed(session)
    # gắn yếu tố KHÔNG khớp tình tiết lên khoản 2 → bị loại ở cổng 2, không vào verified
    eng = ReasoningEngine(
        session, gateway=EchoLLMGateway(),
        elements_by_eid={"nd99__dieu_3__khoan_2": ["yếu tố hoàn toàn không liên quan zzqq"]},
    )
    adj = eng.analyze(CaseInput(facts="vốn pháp định tối thiểu"), as_of=D(2022, 1, 1))

    veids = {a.unit_eid for a in adj.verified_articles}
    assert "nd99__dieu_3__khoan_2" not in veids          # thu hẹp bởi element gate
    assert "nd99__dieu_3__khoan_2__diem_a" in veids       # điều khác (không checklist) vẫn verify


class _RogueGateway(BaseLLMGateway):
    def model_name(self): return "rogue"
    def _draft(self, query, chunks, prompt, as_of, node, lang):
        return "Theo một điều ngoài hồ sơ.", [Citation("nd99__dieu_5", as_of)]


def test_adjudicator_rejects_citation_outside_verified(session: Session):
    _seed(session)
    # Adjudicator trích Điều 5 (ngoài tập verified của query vốn) → abstain
    eng = ReasoningEngine(session, gateway=_RogueGateway())
    adj = eng.analyze(CaseInput(facts="vốn pháp định tối thiểu"), as_of=D(2022, 1, 1))
    assert adj.parties[0].abstain


def test_multi_role_via_analyze(session: Session):
    _seed(session)
    eng = ReasoningEngine(session, gateway=EchoLLMGateway())
    adj = eng.analyze(CaseInput(facts="vốn pháp định tối thiểu"),
                      as_of=D(2022, 1, 1), mode="multi_role")
    assert adj.verified_articles and not adj.parties[0].abstain
