"""Legal Rule Base — thang bậc VBQPPL (lex superior) + quy tắc giải xung đột.

★ SCAFFOLD PROVISIONAL — số rank TẠM, chốt từ primary-text (legal-rule-base.md §6:
Điều 4 Luật 64/2025 + 87/2025). Engine ĐỌC module này (principle #13: tách khỏi engine).

Versioned theo as_of (thang bậc đổi: 2016-07 · 2021-01 · 2025-04 · 2025-07). Scaffold
mới nạp thời kỳ HIỆN HÀNH (từ 2025-07); thêm thời kỳ cũ khi cần vụ quá khứ.
"""

from __future__ import annotations

import datetime as dt

VERIFICATION_STATUS = "provisional"  # ★ X4-fix: loader PHẢI chặn provisional ở production

# rank_level: LỚN HƠN = hiệu lực pháp lý CAO HƠN (khớp JurisdictionPack ví dụ).
# Thời kỳ hiện hành (from 2025-07, Luật 64/2025 + 87/2025) — PROVISIONAL.
_RANK_CURRENT: dict[str, int] = {
    "hien_phap": 100,
    "bo_luat": 90, "luat": 90,            # + nghị quyết Quốc hội
    "phap_lenh": 80,                      # + nghị quyết UBTVQH
    "lenh_ctn": 75, "quyet_dinh_ctn": 75,  # Chủ tịch nước
    "nghi_dinh": 70,
    "quyet_dinh_ttg": 65,                 # Quyết định của Thủ tướng
    "nghi_quyet_hdtp": 60,                # HĐTP TANDTC
    "thong_tu": 50,
    "thong_tu_lien_tich": 45,
    "nghi_quyet_hdnd_tinh": 40,
    "quyet_dinh_ubnd_tinh": 35,
    "quyet_dinh_ctubnd_tinh": 30,         # ★ mới (87/2025)
}

# doc_type mơ hồ theo cơ quan — PHẢI có authority để định rank (nếu không → None/abstain).
_AMBIGUOUS = {"quyet_dinh", "nghi_quyet"}

# map (doc_type, authority_hint) → khóa rank canonical
_AUTHORITY_KEY = {
    ("quyet_dinh", "thu_tuong"): "quyet_dinh_ttg",
    ("quyet_dinh", "chu_tich_nuoc"): "quyet_dinh_ctn",
    ("quyet_dinh", "ubnd_tinh"): "quyet_dinh_ubnd_tinh",
    ("quyet_dinh", "chu_tich_ubnd_tinh"): "quyet_dinh_ctubnd_tinh",
    ("nghi_quyet", "quoc_hoi"): "bo_luat",   # NQ Quốc hội ngang Luật
    ("nghi_quyet", "hdtp"): "nghi_quyet_hdtp",
    ("nghi_quyet", "hdnd_tinh"): "nghi_quyet_hdnd_tinh",
}


def rank_of(doc_type: str, as_of: dt.date, authority_hint: str | None = None) -> int | None:
    """Rank hiệu lực pháp lý. None = không xác định (doc_type mơ hồ thiếu cơ quan)
    → resolve_conflict phải ABSTAIN, không đoán (principle #6)."""
    if doc_type in _AMBIGUOUS:
        key = _AUTHORITY_KEY.get((doc_type, authority_hint))
        return _RANK_CURRENT.get(key) if key else None
    return _RANK_CURRENT.get(doc_type)
