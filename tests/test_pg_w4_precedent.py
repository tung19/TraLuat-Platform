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
