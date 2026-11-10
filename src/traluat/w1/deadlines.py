"""FR-35.13 · Thời hiệu / thời hạn tố tụng — MOAT-ITEM (TVPL chỉ đếm ngày thô).

Tính theo luật tố tụng **@as_of** (bitemporal) + **neo điều luật** (có-nguồn-luật):
- Thời hạn (value+unit) lấy từ reference-data `thoi_hieu` (hiệu-lực-aware) → khi
  BLTTDS/BLDS đổi, thời hạn tự đổi theo ngày. Mỗi mục neo `source_eid`.
- Cộng thời hạn (calendar_vn.add_period) từ `moc_bat_dau` (ngày bắt đầu tính).
- **Ngày cuối rơi vào ngày nghỉ → lùi** sang ngày làm việc kế tiếp (BLTTDS Đ.184),
  dùng lễ dương built-in + lễ âm từ reference (`ngay_nghi`).

Khác calculator thường: ra `DeadlineResult` có `source_eid` + `rolled_from` (minh bạch
đã lùi ngày nghỉ hay chưa). Mơ hồ (không có dữ liệu thời hạn@as_of) → LookupError
(abstain, không đoán — calc sai hại hơn thật thà).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from . import calendar_vn as cal
from .calculators import calculator
from .reference import lookup_reference


@dataclass
class DeadlineResult:
    kind: str
    moc_bat_dau: dt.date          # ngày bắt đầu tính thời hạn
    deadline: dt.date             # ngày hết hạn (đã lùi ngày nghỉ nếu có)
    value: int
    unit: str                     # day | month | year
    source_eid: str | None        # điều luật căn cứ (moat)
    as_of: dt.date
    rolled_from: dt.date | None = None   # ngày gốc nếu đã lùi do rơi ngày nghỉ
    basis: str = ""


def compute_deadline(
    session: Session, kind: str, moc_bat_dau: dt.date, as_of: dt.date, *,
    roll_rest_day: bool = True,
) -> DeadlineResult:
    """Thời hiệu/thời hạn cho `kind` (vd khoi_kien_hop_dong, khang_cao_so_tham_ds,
    khieu_nai_hanh_chinh) tính từ `moc_bat_dau`, theo luật@as_of."""
    rv = lookup_reference(session, "thoi_hieu", kind, as_of)
    if rv is None:
        raise LookupError(f"không có thời hạn {kind}@{as_of} (abstain)")
    value = int(rv.value["value"])
    unit = rv.value["unit"]
    raw = cal.add_period(moc_bat_dau, value, unit)

    rolled_from = None
    deadline = raw
    if roll_rest_day:
        # Lễ âm (Tết/Giỗ Tổ) TÍNH TỰ ĐỘNG (35.14) + override từ reference nếu có.
        # F5: hạn rơi cuối năm rồi lùi → union CẢ raw.year lẫn raw.year+1.
        holidays = set()
        for y in (raw.year, raw.year + 1):
            holidays |= cal.vn_lunar_holidays(y) | cal.holidays_from_reference(session, y, as_of)
        if cal.is_rest_day(raw, holidays):
            deadline = cal.next_business_day(raw, holidays)
            rolled_from = raw

    return DeadlineResult(
        kind=kind, moc_bat_dau=moc_bat_dau, deadline=deadline, value=value, unit=unit,
        source_eid=rv.source_eid, as_of=as_of, rolled_from=rolled_from,
        basis=f"thoi_hieu/{kind}")


@calculator("thoi_hieu")
def _thoi_hieu(session, params, as_of):
    """Expose 35.13 qua toolbox calculator. params={kind, moc_bat_dau(ISO)}."""
    from .calculators import CalcResult
    r = compute_deadline(
        session, params["kind"], dt.date.fromisoformat(params["moc_bat_dau"]), as_of,
        roll_rest_day=params.get("roll_rest_day", True))
    return CalcResult(
        "thoi_hieu",
        {"deadline": r.deadline.isoformat(), "value": r.value, "unit": r.unit,
         "rolled_from": r.rolled_from.isoformat() if r.rolled_from else None},
        r.source_eid, as_of, r.basis)
