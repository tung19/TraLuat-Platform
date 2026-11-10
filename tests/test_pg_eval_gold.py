"""End-to-end (Postgres): load_gold + run_eval + CI gate."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from traluat.core.eval_harness import GoldCase, load_gold, run_eval
from traluat.w1 import build_ingest, load_to_w2
from traluat.w2.db import make_engine
from traluat.w3 import EchoLLMGateway, answer_question

D = dt.date
FRBR = "trl:vn/nd/99/2020"
GOLD = Path(__file__).resolve().parents[1] / "eval" / "gold" / "smoke.jsonl"
from tests.test_w1_structure import SAMPLE  # noqa: E402


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
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


def _answer_fn(s, c):
    return answer_question(s, c.query, as_of=c.as_of, gateway=EchoLLMGateway())


def test_smoke_gold_passes_gate(session: Session):
    cases = load_gold(GOLD)
    assert {c.case_id for c in cases} == {"s1", "s2"}      # bỏ qua dòng '#'
    report = run_eval(session, cases, _answer_fn)
    ok, failures = report.gate({"correct-article": 1.0})
    assert ok, failures


def test_gate_fails_on_missed_article(session: Session):
    # gold trỏ điều KHÔNG truy xuất được cho query → recall 0 → gate fail
    cases = [GoldCase("bad", "vốn pháp định", D(2022, 1, 1),
                      gold_eids=["nd99__dieu_1"], tags=["correct-article"])]
    report = run_eval(session, cases, _answer_fn)
    ok, failures = report.gate({"correct-article": 1.0})
    assert not ok and any("correct-article" in f for f in failures)
