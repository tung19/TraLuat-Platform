"""End-to-end (Postgres): run_eval chấm answer_question trên gold synthetic."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.core.eval_harness import GoldCase, run_eval
from traluat.w1 import build_ingest, load_to_w2
from traluat.w2.db import make_engine
from traluat.w3 import EchoLLMGateway, answer_question

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


def test_run_eval_scores_and_abstention(session: Session):
    load_to_w2(session, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
               units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP")

    cases = [
        GoldCase("c1", "vốn pháp định tối thiểu", D(2022, 1, 1),
                 gold_eids=["nd99__dieu_3__khoan_2"], tags=["correct-article"]),
        GoldCase("c2", "qwxz zzzq kkkplm", D(2022, 1, 1),
                 expect_abstain=True, tags=["trap"]),
    ]
    gw = EchoLLMGateway()
    report = run_eval(session, cases,
                      lambda s, c: answer_question(s, c.query, as_of=c.as_of, gateway=gw))

    assert report.by_tag()["correct-article"]["recall"] == 1.0
    cells = report.abstention_cells()
    assert cells["answer_ok"] == 1 and cells["abstain_ok"] == 1
    assert report.brier() == 0.0        # c1 phủ đủ gold & confidence 1.0
    assert "EVAL REPORT" in report.summary()
