"""CN-05 · Ẩn danh bản án (NQ 03/2017) — che PII cá nhân TRƯỚC khi lưu/công bố.

Bản án công bố PHẢI ẩn danh: tên người → viết tắt, CMND/CCCD/điện thoại/email → che.
Gate tất định (regex), áp ở `ingest_source` cho doc-type bản-án/án-lệ. Trả `(text_sạch,
report)` để audit số lượng đã che. KHÔNG dùng cho văn bản QPPL (Luật/NĐ — không có PII).

Giới hạn (trung thực): tên chỉ che khi đứng sau xưng hô (ông/bà/anh/chị…) — tránh che
nhầm thuật ngữ; tên trần không-xưng-hô cần NER (defer). Địa chỉ chi tiết che số nhà.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Xưng hô dẫn tên người (để neo chỗ che, tránh che nhầm địa danh/thuật ngữ).
_HONORIFIC = r"(?:ông|bà|anh|chị|em|cháu|ông/bà|Ông|Bà|Anh|Chị|bị cáo|nguyên đơn|bị đơn)"
# Chuỗi tên tiếng Việt viết hoa (2–4 từ) sau xưng hô.
_NAME = r"((?:[A-ZÀ-Ỹ][a-zà-ỹ]+\s+){1,3}[A-ZÀ-Ỹ][a-zà-ỹ]+)"

_RULES = [
    ("cccd", re.compile(r"\b\d{12}\b")),                 # CCCD 12 số
    ("cmnd", re.compile(r"\b\d{9}\b")),                  # CMND 9 số
    ("phone", re.compile(r"\b0\d{9}\b")),                # điện thoại
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("so_nha", re.compile(r"\bsố\s+\d+[A-Za-z]?(?:/\d+)*\b", re.IGNORECASE)),  # số nhà
]


@dataclass
class AnonymizeReport:
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def _initials(m: re.Match) -> str:
    """ông Nguyễn Văn An → ông Nguyễn Văn A. (giữ họ+đệm, tên cuối → chữ đầu)."""
    hon, name = m.group(1), m.group(2)
    parts = name.split()
    parts[-1] = parts[-1][0] + "."
    return f"{hon} {' '.join(parts)}"


def anonymize(text: str) -> tuple[str, AnonymizeReport]:
    """Ẩn danh PII trong `text`. Trả (text đã che, report số lượng theo loại)."""
    rep = AnonymizeReport()
    out = text

    name_re = re.compile(rf"\b({_HONORIFIC})\s+{_NAME}")
    out, n = name_re.subn(_initials, out)
    if n:
        rep.counts["ten_nguoi"] = n

    for label, pat in _RULES:
        out, n = pat.subn(f"[{label.upper()}]", out)
        if n:
            rep.counts[label] = n
    return out, rep


# Doc-type bản-án/án-lệ → BẮT BUỘC ẩn danh trước khi lưu (CN-05).
JUDGMENT_TYPES = frozenset({"ban_an", "an_le", "quyet_dinh_toa"})


def is_judgment_type(doc_type: str | None) -> bool:
    return doc_type in JUDGMENT_TYPES
