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
