"""Model THẬT XNLI (mDeBERTa đa ngữ) — NLIVerifier port. @slow (tải ~560MB).

Skip nếu chưa cài extra 'models'."""

from __future__ import annotations

import pytest

pytest.importorskip("transformers")

from traluat.w3.nli_xnli import XNLIVerifier  # noqa: E402

_SRC = "Doanh nghiệp phải nộp hồ sơ trong thời hạn 15 ngày làm việc."


@pytest.fixture(scope="module")
def nli():
    return XNLIVerifier()


def test_entailment_promotes(nli):
    assert nli.supports("Doanh nghiệp cần nộp hồ sơ trong vòng 15 ngày.", _SRC) == "promote"


def test_contradiction_and_unrelated_hold(nli):
    assert nli.supports("Doanh nghiệp không phải nộp hồ sơ.", _SRC) == "hold"
    assert nli.supports("Thủ tục ly hôn được quy định riêng.", _SRC) == "hold"


def test_nli_element_judge_three_way(nli):
    # I1: Gate 2 THẬT bằng NLI — entail→True · contradict→False · neutral→None
    from traluat.w4.element_judge import NLIElementJudge
    j = NLIElementJudge(nli=nli)
    facts = "Doanh nghiệp đã nộp hồ sơ đăng ký kinh doanh đúng thời hạn."
    assert j.judge("doanh nghiệp đã nộp hồ sơ", "", facts) is True
    assert j.judge("doanh nghiệp chưa nộp bất kỳ hồ sơ nào", "", facts) is False
    assert j.judge("doanh nghiệp có trụ sở tại Hà Nội", "", facts) is None
