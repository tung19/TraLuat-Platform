"""Tier-routing (pure) — chọn tầng rẻ-nhất-đủ-dùng."""

from traluat.w3.tier_router import Tier, classify_tier


def test_classify_tier():
    assert classify_tier("mức phạt vi phạm giao thông là bao nhiêu") == Tier.RULE
    assert classify_tier("thời hiệu khởi kiện còn không") == Tier.BITEMPORAL
    assert classify_tier("soạn đơn khởi kiện giúp tôi") == Tier.LLM
    assert classify_tier("điều kiện thành lập doanh nghiệp") == Tier.ML   # default ngữ nghĩa
