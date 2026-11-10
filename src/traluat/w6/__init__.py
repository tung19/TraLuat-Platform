"""W6 — Platform / Portability (slice-1: JurisdictionPack).

JurisdictionPack gom CẤU HÌNH theo vùng tài phán (thang bậc authority_rank · vai
tranh biện · map doc_type mơ hồ · ngôn ngữ) → tách engine khỏi luật-cứng-VN, mở
đường nước thứ 2 (ASEAN). Engine đọc pack; không hardcode. Spec: docs/specs/w6-platform.md.
"""

from .jurisdiction import (
    JurisdictionPack, VN_PACK, get_pack, load_pack, register_pack,
)

__all__ = [
    "JurisdictionPack", "VN_PACK", "get_pack", "load_pack", "register_pack",
]
