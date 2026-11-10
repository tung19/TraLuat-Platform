"""Tier-routing (data-plane §6.1) — chọn tầng RẺ-NHẤT-ĐỦ-DÙNG, đừng gọi LLM cho
việc RULE làm được.

RULE (tra bảng tất định: thuế/lương/phạt/mã) · BITEMPORAL (tính theo luật@T: thời
hiệu/diff/hiệu lực) · LLM (sinh text/giải thích/soạn đơn) · ML (tra mờ/ngữ nghĩa).
Deterministic keyword — không model.
"""

from __future__ import annotations

import re
import unicodedata
from enum import Enum


class Tier(str, Enum):
    RULE = "rule"
    BITEMPORAL = "bitemporal"
    ML = "ml"
    LLM = "llm"


_BITEMPORAL = ("thời hiệu", "hết hạn", "tại ngày", "còn hiệu lực", "hết hiệu lực",
               "so sánh văn bản", "diff", "thay đổi qua")
_RULE = ("thuế suất", "mức thuế", "lương tối thiểu", "mức phạt", "tiền phạt",
         "mã hs", "mã ngành", "tra cứu mã", "bao nhiêu tiền phạt", "lệ phí")
_LLM = ("soạn", "viết đơn", "giải thích", "phân tích", "tư vấn", "vì sao", "tại sao",
        "đánh giá", "nhận định")


def classify_tier(query: str) -> Tier:
    q = unicodedata.normalize("NFC", query).lower()

    def hit(kws):
        return any(k in q for k in kws)

    if hit(_BITEMPORAL):
        return Tier.BITEMPORAL      # tính theo luật@T → query bitemporal W2
    if hit(_RULE):
        return Tier.RULE            # tra bảng reference → KHÔNG model
    if hit(_LLM):
        return Tier.LLM             # sinh/giải thích → RAG qua Gateway
    return Tier.ML                  # mặc định: tra mờ/ngữ nghĩa (retrieve dense)
