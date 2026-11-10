"""Eval harness — metric cấp ký tự (pure)."""

from traluat.core.eval_harness import char_pr


def test_char_pr_overlap():
    p, r = char_pr([(0, 10)], [(5, 15)])   # overlap 5 ký tự
    assert p == 0.5 and r == 0.5


def test_char_pr_exact():
    p, r = char_pr([(0, 20)], [(0, 20)])
    assert p == 1.0 and r == 1.0


def test_char_pr_disjoint():
    p, r = char_pr([(0, 5)], [(10, 20)])
    assert p == 0.0 and r == 0.0
