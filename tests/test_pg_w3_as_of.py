"""End-to-end (Postgres): answer_with_resolution — event-date-first đưa ra điều
còn hiệu lực TẠI NGÀY SỰ KIỆN, dù nay đã hết; mốc không chắc → caveat."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2 import repo
from traluat.w2.bitemporal import EffectStatus
from traluat.w2.db import make_engine
from traluat.w3 import EchoLLMGateway, answer_question, answer_with_resolution

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
    load_to_w2(session, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
               units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP")
    repo.repeal(session, "nd99__dieu_5", D(2023, 6, 1))  # Điều 5 hết hiệu lực 2023


def test_event_date_first_surfaces_era_law(session: Session):
    _seed(session)
    q = "cơ quan đăng ký kinh doanh có thẩm quyền"

    # Multiple criminal-law anchors require a human applicability comparison.
    ans, plan = answer_with_resolution(
        session, q, question_type="hinh_su",
        event_date=D(2022, 1, 1), today=D(2024, 1, 1), gateway=EchoLLMGateway(),
    )
    assert plan.anchors == [D(2022, 1, 1), D(2024, 1, 1)] and plan.lenient_fetch
    assert ans.abstain and ans.needs_human and ans.caveat
    relevant = [c for c in ans.review_context if c["unit_eid"] == "nd99__dieu_5"]
    assert {c["anchor"] for c in relevant} == {"2022-01-01", "2024-01-01"}
    assert any(c["effect_status"] == EffectStatus.IN_FORCE.value for c in relevant)

    # Hỏi 'nay' (2024) thuần: Điều 5 đã chết → cổng chặn, KHÔNG cite Điều 5
    plain = answer_question(session, q, as_of=D(2024, 1, 1), gateway=EchoLLMGateway())
    assert "nd99__dieu_5" not in plain.citations


def test_missing_event_date_criminal_caveat(session: Session):
    _seed(session)
    ans, plan = answer_with_resolution(
        session, "điều kiện kinh doanh gồm những gì", question_type="hinh_su",
        today=D(2024, 1, 1), gateway=EchoLLMGateway(),
    )
    assert plan.needs_human                      # không có mốc sự kiện
    if not ans.abstain:                          # nếu có trả lời → phải kèm caveat
        assert ans.caveat and ans.confidence <= 0.6
