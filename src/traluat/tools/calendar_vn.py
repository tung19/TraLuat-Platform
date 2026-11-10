"""FR-35.14 · Lịch & đếm ngày (nền cho 35.13 thời hiệu tố tụng).

Số học ngày/tháng/năm theo cách luật VN tính thời hạn, + quy tắc ngày nghỉ:
- Thời hạn tính bằng **ngày**: `add_period(start, n, "day")` = start + n ngày.
- Tính bằng **tháng/năm**: cùng ngày của tháng/năm sau; nếu tháng đích không có ngày
  đó (vd 31 → tháng 2) thì lấy ngày cuối tháng (kẹp cuối tháng).
- **Ngày cuối rơi vào ngày nghỉ** (thứ 7/CN hoặc ngày lễ) → lùi sang NGÀY LÀM VIỆC
  kế tiếp (BLTTDS Đ.184). `next_business_day`.

Ngày lễ: phần cố định dương lịch là built-in; phần ÂM LỊCH (Tết, Giỗ Tổ) đổi theo năm
→ lấy từ reference-data (`holidays_from_reference`, dataset `ngay_nghi` đội data đẩy),
KHÔNG tự suy (tránh thuật toán âm lịch sai). Chuyển đổi âm-dương đầy đủ = defer (cần
ephemeris) — ở đây dùng bảng ngày lễ theo năm.
"""

from __future__ import annotations

import calendar
import datetime as dt

D = dt.date

# Ngày lễ CỐ ĐỊNH dương lịch (BLLĐ Đ.112) — phần không phụ thuộc âm lịch.
_FIXED_SOLAR = [(1, 1), (4, 30), (5, 1), (9, 2)]   # Tết dương · 30/4 · 1/5 · Quốc khánh


def vn_fixed_solar_holidays(year: int) -> set[dt.date]:
    """Ngày lễ dương-lịch cố định trong năm (Tết âm/Giỗ Tổ lấy từ reference-data)."""
    return {D(year, m, d) for m, d in _FIXED_SOLAR}


def is_weekend(d: dt.date) -> bool:
    return d.weekday() >= 5                          # 5=T7, 6=CN


def is_rest_day(d: dt.date, holidays: set[dt.date] | None = None) -> bool:
    """Ngày nghỉ = cuối tuần HOẶC ngày lễ (built-in dương + holidays truyền vào)."""
    if is_weekend(d):
        return True
    hol = vn_fixed_solar_holidays(d.year)
    if holidays:
        hol = hol | holidays
    return d in hol


def next_business_day(d: dt.date, holidays: set[dt.date] | None = None) -> dt.date:
    """Nếu `d` là ngày nghỉ → lùi sang ngày làm việc kế tiếp (lặp tới khi là ngày làm)."""
    cur = d
    while is_rest_day(cur, holidays):
        cur += dt.timedelta(days=1)
    return cur


def count_days(a: dt.date, b: dt.date) -> int:
    """Số ngày từ a đến b (b - a). Âm nếu b < a."""
    return (b - a).days


def add_days(start: dt.date, n: int) -> dt.date:
    return start + dt.timedelta(days=n)


def _add_months(start: dt.date, months: int) -> dt.date:
    m0 = start.month - 1 + months
    year = start.year + m0 // 12
    month = m0 % 12 + 1
    last = calendar.monthrange(year, month)[1]       # kẹp cuối tháng (31→28/30)
    return D(year, month, min(start.day, last))


def add_period(start: dt.date, value: int, unit: str) -> dt.date:
    """Cộng thời hạn: unit ∈ {day, month, year}. Tháng/năm kẹp cuối tháng."""
    if unit == "day":
        return add_days(start, value)
    if unit == "month":
        return _add_months(start, value)
    if unit == "year":
        return _add_months(start, value * 12)
    raise ValueError(f"unit không hợp lệ: {unit} (day|month|year)")


def vn_lunar_holidays(year: int) -> set[dt.date]:
    """Ngày lễ ÂM tính từ thuật toán âm lịch (35.14) — KHÔNG cần reference:
    Tết (30 Chạp → mùng 4, bao trọn 5 ngày nghỉ BLLĐ) + Giỗ Tổ 10/3 âm."""
    from .lunar import gio_to_date, tet_date
    tet = tet_date(year)
    days = {tet + dt.timedelta(days=o) for o in range(-1, 5)}   # 30 Chạp..mùng 4
    days.add(gio_to_date(year))
    return days


def vn_holidays(year: int) -> set[dt.date]:
    """Toàn bộ ngày lễ VN năm `year` = dương cố định + âm (tính tự động)."""
    return vn_fixed_solar_holidays(year) | vn_lunar_holidays(year)


def holidays_from_reference(session, year: int, as_of: dt.date) -> set[dt.date]:
    """Ngày lễ ÂM-lịch-phái-sinh (Tết, Giỗ Tổ…) của `year` từ reference-data
    (dataset `ngay_nghi`, key=str(year), value={"dates": ["YYYY-MM-DD", ...]}).
    Không có dữ liệu → trả rỗng (chỉ còn lễ dương built-in)."""
    from .reference import lookup_reference
    rv = lookup_reference(session, "ngay_nghi", str(year), as_of)
    if rv is None:
        return set()
    return {dt.date.fromisoformat(x) for x in rv.value.get("dates", [])}
