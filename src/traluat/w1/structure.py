"""Stage 3 — cấu trúc hóa văn bản luật VN + eId ổn định (pattern Bluebell).

Deterministic (RULE), KHÔNG model. eId = {doc_slug}__{alias}_{num}, lồng theo cha.
Lưu ý VN: số Điều là TOÀN VĂN BẢN (không theo Chương) → eid Điều không lồng dưới
Chương; nhưng CÂY (parent) đặt Điều dưới Chương để document_as_of ghép đúng thứ bậc.

Phạm vi slice-1: Chương · Mục · Điều · Khoản · Điểm. Phần/Tiểu mục thêm sau.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _roman_to_int(s: str) -> int:
    s = s.upper()
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN.get(ch, 0)
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def _diem_ord(letter: str) -> int:
    # a,b,c,… đ xếp sau d (bảng chữ cái VN) — đủ cho đánh thứ tự
    order = "abcdđefghijklmnopqrstuvwxyz"
    return order.index(letter.lower()) + 1 if letter.lower() in order else 0


@dataclass
class ParsedUnit:
    eid: str
    unit_type: str          # chuong|muc|dieu|khoan|diem
    ordinal: int
    label: str
    parent_eid: str | None
    text: str | None        # None cho đơn vị kết cấu (Chương/Mục) không có nội dung riêng


# regex biên (dòng đã strip). NFC trước khi match.
_RE_CHUONG = re.compile(r"^Chương\s+([IVXLCDM]+|\d+)\b\.?\s*(.*)$", re.IGNORECASE)
_RE_MUC = re.compile(r"^Mục\s+(\d+)\b\.?\s*(.*)$", re.IGNORECASE)
_RE_DIEU = re.compile(r"^Điều\s+(\d+)\s*[.．]?\s*(.*)$")
_RE_KHOAN = re.compile(r"^(\d+)[.)]\s+(.+)$")
_RE_DIEM = re.compile(r"^([a-zđ])\)\s+(.+)$", re.IGNORECASE)


def parse_structure(text: str, doc_slug: str) -> list[ParsedUnit]:
    text = unicodedata.normalize("NFC", text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    units: list[ParsedUnit] = []
    cur_container: str | None = None   # chương/mục đang mở (parent cây của Điều)
    cur_chuong: str | None = None
    cur_dieu: str | None = None
    cur_khoan: str | None = None
    cur_diem: str | None = None
    by_eid: dict[str, ParsedUnit] = {}

    def add(u: ParsedUnit) -> None:
        if u.eid in by_eid:
            raise ValueError(f"đơn vị trùng eId, cần duyệt cấu trúc: {u.eid}")
        units.append(u)
        by_eid[u.eid] = u

    for ln in lines:
        if (m := _RE_CHUONG.match(ln)):
            n = _roman_to_int(m.group(1)) if not m.group(1).isdigit() else int(m.group(1))
            eid = f"{doc_slug}__chuong_{n}"
            add(ParsedUnit(eid, "chuong", n, f"Chương {m.group(1).upper()}", None, None))
            cur_chuong = cur_container = eid
            cur_dieu = cur_khoan = cur_diem = None
        elif (m := _RE_MUC.match(ln)):
            n = int(m.group(1))
            eid = f"{cur_chuong or doc_slug}__muc_{n}"
            add(ParsedUnit(eid, "muc", n, f"Mục {n}", cur_chuong, None))
            cur_container = eid
            cur_dieu = cur_khoan = cur_diem = None
        elif (m := _RE_DIEU.match(ln)):
            n = int(m.group(1))
            eid = f"{doc_slug}__dieu_{n}"
            title = m.group(2).strip()
            add(ParsedUnit(eid, "dieu", n, f"Điều {n}", cur_container, title or None))
            cur_dieu, cur_khoan, cur_diem = eid, None, None
        elif cur_dieu and (m := _RE_DIEM.match(ln)) and cur_khoan:
            letter = m.group(1).lower()
            eid = f"{cur_khoan}__diem_{letter}"
            add(ParsedUnit(eid, "diem", _diem_ord(letter), letter, cur_khoan, m.group(2).strip()))
            cur_diem = eid
        elif cur_dieu and (m := _RE_KHOAN.match(ln)):
            n = int(m.group(1))
            eid = f"{cur_dieu}__khoan_{n}"
            add(ParsedUnit(eid, "khoan", n, str(n), cur_dieu, m.group(2).strip()))
            cur_khoan = eid
            cur_diem = None
        else:
            # dòng nối tiếp → gắn vào đơn vị nội dung gần nhất
            tgt = cur_diem or cur_khoan or cur_dieu
            if tgt and by_eid[tgt].text is not None:
                by_eid[tgt].text += " " + ln
            elif tgt:
                by_eid[tgt].text = ln

    return units
