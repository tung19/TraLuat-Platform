"""End-to-end (Postgres): precedent store nuôi prune — án lệ mất điểm tựa bị bỏ."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2 import repo
from traluat.w2.db import make_engine
from traluat.w3 import EchoLLMGateway
from traluat.w4 import CaseInput, ReasoningEngine, add_precedent

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
    if conn.execute(sa.text("select to_regclass('public.precedent')")).scalar() is None:
        trans.rollback(); conn.close()
        pytest.skip("precedent chưa migrate")
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


def test_precedent_matched_and_pruned(session: Session):
    repo.repeal(session, "nd99__dieu_5", D(2023, 6, 1))        # Điều 5 hết hiệu lực 2023
    add_precedent(session, "AL01", ["nd99__dieu_3__khoan_2"], situation="vốn")   # tựa điều SỐNG
    add_precedent(session, "AL03", ["nd99__dieu_5"], situation="thẩm quyền")     # tựa điều CHẾT

    eng = ReasoningEngine(session, gateway=EchoLLMGateway())
    adj = eng.analyze(
        CaseInput(facts="vốn pháp định tối thiểu thẩm quyền đăng ký kinh doanh"),
        as_of=D(2024, 1, 1))

    pids = {p.precedent_id for p in adj.verified_precedents}
    assert "AL01" in pids          # tựa Điều còn hiệu lực → giữ
    assert "AL03" not in pids      # tựa Điều hết hiệu lực (bị Auditor loại) → prune


def test_binding_precedents_effectivity(session: Session):
    # CN-04: án lệ chỉ RÀNG BUỘC từ effective_from; trước đó không áp
    from traluat.w4.precedent_store import add_precedent, binding_precedents
    add_precedent(session, "AL-10/2020", ["nd99__dieu_3"],
                  effective_from=D(2020, 6, 1))
    add_precedent(session, "AL-null", ["nd99__dieu_3"])      # NULL → luôn áp

    before = {p.precedent_id for p in binding_precedents(session, ["nd99__dieu_3"], D(2020, 1, 1))}
    after = {p.precedent_id for p in binding_precedents(session, ["nd99__dieu_3"], D(2021, 1, 1))}
    assert "AL-10/2020" not in before and "AL-null" in before      # chưa hiệu lực
    assert "AL-10/2020" in after and "AL-null" in after            # đã ràng buộc
    # không tựa eid trong tình huống → không áp
    assert binding_precedents(session, ["nd99__dieu_1"], D(2021, 1, 1)) == []


def test_judgment_flags_missing_binding_precedent(session: Session):
    from traluat.w4.precedent_store import add_precedent
    from traluat.w6 import JudgmentAnalysisService
    add_precedent(session, "AL-01/2016/AL", ["nd99__dieu_3"], effective_from=D(2016, 1, 1))
    # bản án viện điều nhưng BỎ án lệ ràng buộc → cờ (CN-04)
    f = JudgmentAnalysisService(session).analyze(
        ["nd99__dieu_3"], ["nd99__dieu_3"], D(2022, 1, 1))
    assert f.flagged and "AL-01/2016/AL" in f.missing_precedents
    # nếu viện cả án lệ → không cờ
    f2 = JudgmentAnalysisService(session).analyze(
        ["nd99__dieu_3"], ["nd99__dieu_3"], D(2022, 1, 1),
        cited_precedents=["AL-01/2016/AL"])
    assert not f2.flagged
