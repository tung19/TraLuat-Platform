"""Stage 4 — trích metadata từ đầu/cuối văn bản (RULE regex, không model).

Header VB VN rất cố định → bắt được chắc:
  "Số: 99/2020/NĐ-CP"                         → doc_number + doc_type (từ hậu tố)
  "CHÍNH PHỦ" / "QUỐC HỘI" / "BỘ TÀI CHÍNH"   → authority_name
  "Hà Nội, ngày 15 tháng 6 năm 2020"          → date_issued
  "có hiệu lực thi hành kể từ ngày 01 tháng   → date_effective
   01 năm 2021" | "kể từ ngày ký"             →   (ngày ký → = date_issued)

Thiếu trường nào để None — KHÔNG đoán. doc_type suy từ hậu tố số hiệu (nguồn
đáng tin hơn mọi heuristic khác); hậu tố lạ → doc_type=None (chờ người xác định,
không gán bừa — ảnh hưởng authority_rank nên không được sai).
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass

# số hiệu + hậu tố loại VB: 99/2020/NĐ-CP · 59/2020/QH14 · 15/2012/TT-BTC
_RE_SO = re.compile(r"\bSố:?\s*(\d+/\d{4}/([A-ZĐ][A-ZĐ0-9]*(?:-[A-ZĐ0-9]+)*))", re.IGNORECASE)
_RE_NGAY_KY = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})")
_RE_HIEU_LUC = re.compile(
    r"có hiệu lực(?:\s+thi hành)?\s+kể từ ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
    re.IGNORECASE,
)
_RE_HIEU_LUC_KY = re.compile(r"có hiệu lực(?:\s+thi hành)?\s+(?:kể\s+)?từ ngày ký", re.IGNORECASE)

# hậu tố số hiệu → doc_type canonical (khớp legal_rule_base)
_SUFFIX_TYPE = {
    "NĐ-CP": "nghi_dinh",
    "TT": "thong_tu",       # TT-BTC, TT-BXD… (khớp prefix 'TT')
    "QĐ": "quyet_dinh",     # QĐ-TTg, QĐ-BTC…
    "NQ": "nghi_quyet",     # NQ-CP, NQ-HĐND…
    "PL": "phap_lenh",
    "QH": "luat",           # 59/2020/QH14 → Luật (hậu tố QH<khóa>)
    "UBTVQH": "phap_lenh",
}

# ★ cụ thể/bao-hàm trước: 'THỦ TƯỚNG CHÍNH PHỦ' phải đứng trước 'CHÍNH PHỦ',
# 'ỦY BAN THƯỜNG VỤ QUỐC HỘI' trước 'QUỐC HỘI' — else substring nuốt mất.
_AUTHORITIES = [
    "ỦY BAN THƯỜNG VỤ QUỐC HỘI", "THỦ TƯỚNG CHÍNH PHỦ",
    "TÒA ÁN NHÂN DÂN TỐI CAO", "VIỆN KIỂM SÁT NHÂN DÂN TỐI CAO", "CHỦ TỊCH NƯỚC",
    "QUỐC HỘI", "CHÍNH PHỦ",
]


@dataclass
class DocMeta:
    doc_number: str | None = None
    doc_type: str | None = None
    authority_name: str | None = None
    date_issued: dt.date | None = None
    date_effective: dt.date | None = None


def _mk_date(d: str, mo: str, y: str) -> dt.date | None:
    try:
        return dt.date(int(y), int(mo), int(d))
    except ValueError:
        return None


def _doc_type_from_suffix(suffix: str) -> str | None:
    s = suffix.upper()
    for key, val in _SUFFIX_TYPE.items():
        if s == key or s.startswith(key + "-") or (key == "QH" and s.startswith("QH")):
            return val
    return None


def extract_metadata(text: str) -> DocMeta:
    """Quét header + điều khoản thi hành → DocMeta. Pure; không chạm DB."""
    text = unicodedata.normalize("NFC", text)
    meta = DocMeta()

    if (m := _RE_SO.search(text)):
        meta.doc_number = m.group(1)
        meta.doc_type = _doc_type_from_suffix(m.group(2))

    low_upper = text.upper()
    for auth in _AUTHORITIES:  # cụ thể trước (list đã xếp dài/cụ thể hợp lý)
        if auth in low_upper:
            meta.authority_name = auth
            break

    if (m := _RE_NGAY_KY.search(text)):
        meta.date_issued = _mk_date(*m.groups())

    if (m := _RE_HIEU_LUC.search(text)):
        meta.date_effective = _mk_date(*m.groups())
    elif _RE_HIEU_LUC_KY.search(text):
        meta.date_effective = meta.date_issued  # 'kể từ ngày ký' → = ngày ban hành

    return meta
