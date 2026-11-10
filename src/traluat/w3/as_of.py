"""resolve_as_of (§1b / C3) — chọn MỐC theo NGÀY SỰ KIỆN, không mặc định 'hôm nay'.

Bất biến pháp lý:
- as_of = ngày SỰ KIỆN (ký HĐ / hành vi / tranh chấp), KHÔNG phải ngày hỏi. Review
  xài ngày thực hiện. (C3a)
- Hình sự lex-mitior (BLHS Đ.7): luật tại thời điểm phạm tội áp dụng, TRỪ KHI luật
  sau NHẸ HƠN → nạp THÊM mốc 'hiện nay' để tầng sau so favorability (fetch-newer).
- Không giải được mốc sự kiện cho loại nhạy-hồi-tố → cờ needs_human (KHÔNG đoán today).

KHÔNG tự quyết luật nào thắng (đó là W2 resolve_conflict / governing_candidates) —
chỉ nói RETRIEVE tại những mốc nào.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field

# loại câu nhạy hồi-tố: thiếu mốc sự kiện = KHÔNG được đoán today (phải HITL)
_RETRO_SENSITIVE = {"hinh_su", "xu_phat"}
_LEX_MITIOR = {"hinh_su"}

_RE_DMY = re.compile(r"\bngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})")
_RE_SLASH = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
_RE_YEAR = re.compile(r"\bnăm\s+(\d{4})\b")


def _first_event_date(query: str) -> dt.date | None:
    q = unicodedata.normalize("NFC", query)
    if (m := _RE_DMY.search(q)):
        d, mo, y = (int(x) for x in m.groups())
    elif (m := _RE_SLASH.search(q)):
        d, mo, y = (int(x) for x in m.groups())
    elif (m := _RE_YEAR.search(q)):
        d, mo, y = 1, 1, int(m.group(1))   # 'năm Y' → 01/01/Y (đại diện, kém chính xác)
    else:
        return None
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


@dataclass
class AsOfPlan:
    anchors: list[dt.date]         # các mốc để retrieve (≥1), primary đứng đầu
    primary: dt.date               # mốc trả lời/verify mặc định
    lenient_fetch: bool = False    # hình sự: đã nạp thêm mốc 'nay' để so lex-mitior
    needs_human: bool = False      # không giải được mốc sự kiện (nhạy hồi-tố)
    reason: str = ""


def resolve_as_of(
    query: str, question_type: str = "general", *,
    event_date: dt.date | None = None, today: dt.date | None = None,
) -> AsOfPlan:
    today = today or dt.date.today()
    anchor = event_date or _first_event_date(query)
    needs_human = False

    if anchor is None:
        anchor = today
        needs_human = question_type in _RETRO_SENSITIVE
        reason = "no_event_date:fallback_today" + ("→HITL" if needs_human else "")
    else:
        reason = "event_date" if event_date else "event_date:from_query"

    anchors = [anchor]
    lenient = False
    if question_type in _LEX_MITIOR and anchor != today:
        anchors = [anchor, today]   # luật-lúc-phạm vs luật-nay → tầng sau chọn nhẹ hơn
        lenient = True
        reason += ";lex_mitior:fetch_newer"

    return AsOfPlan(anchors=anchors, primary=anchor, lenient_fetch=lenient,
                    needs_human=needs_human, reason=reason)
