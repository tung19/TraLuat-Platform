"""FR-41 — trích đại lượng + token chủ đề (pure)."""

from traluat.w3.conflict_detect import _quantities, _topic_tokens


def test_quantities():
    assert _quantities("30 ngày") == {"ngày": {30}}
    assert _quantities("15 ngày và 20 tỷ đồng") == {"ngày": {15}, "tỷ": {20}}


def test_topic_tokens_drop_numbers_units_stopwords():
    toks = _topic_tokens("Thời hạn nộp hồ sơ là 30 ngày")
    assert "ngày" not in toks and "30" not in toks and "là" not in toks
    assert {"thời", "hạn", "nộp", "hồ", "sơ"} <= toks
