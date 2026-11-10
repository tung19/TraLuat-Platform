"""NLI stub — nhánh promote/hold (pure)."""

from traluat.w3 import KeywordNLIVerifier


def test_promote_when_claim_supported():
    nli = KeywordNLIVerifier(threshold=0.6)
    assert nli.supports("doanh nghiệp nộp hồ sơ",
                        "Doanh nghiệp phải nộp hồ sơ trong thời hạn.") == "promote"


def test_hold_when_divergent():
    nli = KeywordNLIVerifier(threshold=0.6)
    assert nli.supports("mức phạt tử hình", "quy định về đăng ký kinh doanh") == "hold"
    assert nli.supports("", "bất kỳ") == "hold"
