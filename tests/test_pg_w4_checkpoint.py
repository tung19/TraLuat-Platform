"""End-to-end (Postgres): durable checkpointer — resume không audit lại + prefix guard."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2.db import make_engine
from traluat.w3 import EchoLLMGateway
from traluat.w4 import (
    CaseInput,
    CrossTenantCheckpoint,
    DebateCheckpoint,
    InMemoryCheckpointer,
    MultiRoleReasoner,
    PostgresCheckpointer,
    RoleConfig,
)

D = dt.date
FRBR = "trl:vn/nd/99/2020"
from tests.test_w1_structure import SAMPLE

ROLES = [RoleConfig("lawyer", "quyền lợi"), RoleConfig("judge", "")]
ELEMENTS = {"nd99__dieu_3__khoan_2": ["vốn pháp định"]}   # 1 điều có checklist → gọi judge


class CountingJudge:
    checkpoint_version = "counting-keyword-v1"

    def __init__(self):
        from traluat.w4 import KeywordElementJudge
        self.calls = 0
        self._inner = KeywordElementJudge()

    def judge(self, element, law_text, party_facts):
        self.calls += 1
        return self._inner.judge(element, law_text, party_facts)


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    DebateCheckpoint.__table__.create(bind=conn, checkfirst=True)  # rollback sẽ bỏ
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


def _mr(session, judge):
    return MultiRoleReasoner(session, gateway=EchoLLMGateway(), roles=ROLES,
                             element_judge=judge, elements_by_eid=ELEMENTS, max_rounds=3)


CASE = CaseInput(facts="vốn pháp định tối thiểu của doanh nghiệp")


def test_resume_skips_reaudit(session: Session):
    cp = InMemoryCheckpointer()
    j1 = CountingJudge()
    r1 = _mr(session, j1).run(CASE, D(2022, 1, 1), tenant_id="t1", case_id="c1", checkpointer=cp)
    assert j1.calls > 0                                   # lần đầu có audit element

    j2 = CountingJudge()
    r2 = _mr(session, j2).run(CASE, D(2022, 1, 1), tenant_id="t1", case_id="c1", checkpointer=cp)
    assert j2.calls == 0                                  # resume → KHÔNG audit lại (H4 persist)
    assert {a.unit_eid for a in r1.adjudication.verified_articles} == \
           {a.unit_eid for a in r2.adjudication.verified_articles}


def test_postgres_checkpointer_roundtrip_and_prefix(session: Session):
    cp = PostgresCheckpointer(session)
    cp.save("tenant:t1:c9", "t1", {"round": 1, "pool_eids": ["nd99__dieu_1"]})
    assert cp.load("tenant:t1:c9", "t1")["pool_eids"] == ["nd99__dieu_1"]
    # ★ C3: tenant khác đọc cùng thread → chặn (checkpointer không có RLS)
    with pytest.raises(CrossTenantCheckpoint):
        cp.load("tenant:t1:c9", "t2")


def test_resume_reaudits_after_canonical_amendment(session: Session):
    from traluat.w2 import repo
    cp = InMemoryCheckpointer()
    first = CountingJudge()
    _mr(session, first).run(CASE, D(2022, 1, 1), tenant_id="t1", case_id="c1", checkpointer=cp)
    assert first.calls > 0
    repo.apply_amendment(session, "nd99__dieu_3__khoan_2",
                         "Mức vốn pháp định tối thiểu là 30 tỷ đồng.", D(2022, 1, 1),
                         source_relation_id="checkpoint-regression")
    second = CountingJudge()
    _mr(session, second).run(CASE, D(2022, 1, 1), tenant_id="t1", case_id="c1", checkpointer=cp)
    assert second.calls > 0  # the old verified pool must not survive a KB change
