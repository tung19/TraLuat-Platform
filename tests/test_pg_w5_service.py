"""End-to-end (Postgres): LegalService — residency routing + audit quanh engine."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2.db import make_engine
from traluat.w3 import EchoLLMGateway
from traluat.w4 import CaseInput
from traluat.w5 import LegalService, LLMDestination, TenantContext

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


def _svc(session: Session) -> LegalService:
    load_to_w2(session, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
               units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP")
    return LegalService(session, local_gateway=EchoLLMGateway(),
                        claude_gateway=EchoLLMGateway())


CASE = CaseInput(facts="vốn pháp định tối thiểu của doanh nghiệp")
CTX = TenantContext("t1", role="lawyer")


def test_client_data_routes_local_and_audits(session: Session):
    svc = _svc(session)
    r = svc.analyze(CASE, D(2022, 1, 1), CTX, client_data=True, local_available=True)

    assert r.answered and r.route.destination == LLMDestination.LOCAL
    assert r.ai_label is True and r.trace_id
    assert not r.adjudication.parties[0].abstain
    phases = [e.phase for e in svc.audit.by_trace(r.trace_id)]
    assert phases == ["intent", "done"]              # write-ahead rồi confirm


def test_client_data_local_down_denies_never_claude(session: Session):
    svc = _svc(session)
    r = svc.analyze(CASE, D(2022, 1, 1), CTX, client_data=True, local_available=False)

    assert not r.answered and r.route.destination == LLMDestination.DENY  # ★ R2
    assert r.route.destination != LLMDestination.CLAUDE
    assert r.reason.startswith("egress_denied")
    assert r.ai_label is True and r.trace_id            # vẫn gắn nhãn + trace
    assert [e.phase for e in svc.audit.by_trace(r.trace_id)] == ["intent", "denied"]


def test_public_lookup_allowed_to_claude(session: Session):
    svc = _svc(session)
    r = svc.analyze(CASE, D(2022, 1, 1), CTX, client_data=False, local_available=True)
    assert r.route.destination == LLMDestination.CLAUDE   # dữ liệu công → ra ngoài được
    assert r.answered
