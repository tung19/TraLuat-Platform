"""End-to-end (Postgres): MultiRoleReasoner — Auditor mọi phát ngôn + stop
deterministic (hội tụ set-equality / max_rounds). W4 §7.6–7."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2 import repo
from traluat.w2.db import make_engine
from traluat.w3 import EchoLLMGateway
from traluat.w4 import CaseInput, MultiRoleReasoner, RoleConfig

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


ROLES = [RoleConfig("lawyer", "quyền lợi"), RoleConfig("judge", "")]


def test_converges_by_set_equality(session: Session):
    _seed(session)
    mr = MultiRoleReasoner(session, gateway=EchoLLMGateway(), roles=ROLES, max_rounds=5)
    res = mr.run(CaseInput(facts="vốn pháp định tối thiểu doanh nghiệp"),
                 as_of=D(2022, 1, 1), tenant_id="t1", case_id="c1")

    # lượt 2 không thêm căn cứ verified nào (retrieve tất định) → hội tụ, KHÔNG chạm max_rounds
    assert res.converged and res.rounds == 2
    assert res.thread_id == "tenant:t1:c1"           # không timestamp
    assert len(res.transcript) == len(ROLES) * 2
    assert res.adjudication.verified_articles and not res.adjudication.parties[0].abstain
    assert res.adjudication.audit_trail             # B6: debate mode có trail (không rỗng)


def test_stops_at_max_rounds(session: Session):
    _seed(session)
    mr = MultiRoleReasoner(session, gateway=EchoLLMGateway(), roles=ROLES, max_rounds=1)
    res = mr.run(CaseInput(facts="vốn pháp định tối thiểu"), as_of=D(2022, 1, 1))
    assert res.rounds == 1 and not res.converged      # dừng do ngân sách lượt


def test_auditor_strikes_expired_in_every_utterance(session: Session):
    _seed(session)
    repo.repeal(session, "nd99__dieu_5", D(2023, 6, 1))   # Điều 5 hết hiệu lực 2023
    mr = MultiRoleReasoner(
        session, gateway=EchoLLMGateway(),
        roles=[RoleConfig("judge", "thẩm quyền đăng ký")], max_rounds=1)
    # hỏi tại 2024: nếu Điều 5 được 1 vai đề xuất, Auditor phải GẠCH (hết hiệu lực)
    res = mr.run(CaseInput(facts="cơ quan đăng ký kinh doanh có thẩm quyền"),
                 as_of=D(2024, 1, 1))
    for u in res.transcript:
        assert "nd99__dieu_5" not in u.verified_eids   # không vai nào 'thắng' bằng điều đã chết
    assert all(a.unit_eid != "nd99__dieu_5" for a in res.adjudication.verified_articles)
