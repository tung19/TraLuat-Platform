"""The release gate must use required-obligation coverage, not article recall."""
import datetime as dt

from traluat.core.eval_harness import EvalReport, GoldCase, run_eval
from traluat.w3 import Answer


def test_missing_required_obligation_fails_even_with_perfect_article_recall():
    case = GoldCase("omission", "q", dt.date(2020, 1, 1), gold_eids=["a"],
                    required_eids=["a", "b"], tags=["omission"])
    report = run_eval(None, [case], lambda *_: Answer(False, citations=["a"], confidence=1))
    assert report.results[0].recall == 1
    assert report.by_tag()["omission"]["omission_recall"] == 0.5
    ok, reasons = report.gate({"omission": 1})
    assert not ok and any("omission_recall" in r for r in reasons)
    assert report.brier() == 1


def test_complete_required_obligations_pass_omission_gate():
    case = GoldCase("omission", "q", dt.date(2020, 1, 1), gold_eids=["a", "b"],
                    required_eids=["a", "b"], tags=["omission"])
    report = run_eval(None, [case], lambda *_: Answer(False, citations=["a", "b"], confidence=1))
    assert report.gate({"omission": 1}) == (True, [])


def test_empty_evaluation_cannot_pass_release_gate():
    assert not EvalReport([]).gate()[0]
