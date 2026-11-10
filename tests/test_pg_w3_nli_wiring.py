"""End-to-end (Postgres): NLI gate3 nối vào ground — verdict promote ghi lên gate."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2.db import make_engine
from traluat.w3 import KeywordNLIVerifier, ground

D = dt.date
from tests.test_w1_structure import SAMPLE  # noqa: E402


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    s = Session(bind=conn, future=True)
    load_to_w2(s, frbr_uri="trl:vn/nd/99/2020", doc_type="nghi_dinh",
               date_effective=D(2021, 1, 1), units=build_ingest(SAMPLE, "nd99"),
               doc_number="99/2020/NĐ-CP")
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def test_nli_promote_recorded_on_gate(session: Session):
    eid = "nd99__dieu_3__khoan_1"
    claim = "Doanh nghiệp phải nộp hồ sơ trong thời hạn 15 ngày làm việc."
    g = ground(session, claim, D(2022, 1, 1), [eid], "vi", KeywordNLIVerifier())
    assert not g.abstain
    assert g.gates[0].gate3_nli == "promote"       # nguồn hỗ trợ → promote (không veto)
