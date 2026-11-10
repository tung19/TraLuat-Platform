"""W3 exactness (gate3b) — trích đại lượng số/ngày (pure, không cần DB)."""

from traluat.w3.grounding import _facts


def test_facts_extraction():
    assert _facts("nộp hồ sơ trong 15 ngày làm việc") == {"15 ngày"}
    assert _facts("vốn 20 tỷ đồng, có hiệu lực kể từ ngày 01/6/2023") == {"20 tỷ", "01/06/2023"}
    # 'Điều 3' KHÔNG phải đại lượng → không bắt (tránh nhiễu số hiệu điều)
    assert _facts("Điều 3 quy định chung") == set()


def test_facts_mismatch_detectable():
    claim = _facts("phải nộp trong 30 ngày")
    source = _facts("phải nộp trong 15 ngày làm việc")
    assert claim - source == {"30 ngày"}   # gate3b sẽ chặn: 15 ngày ≠ 30 ngày
