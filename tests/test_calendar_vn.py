"""FR-35.14 · lịch & đếm ngày (thuần, không DB)."""

from __future__ import annotations

import datetime as dt

from traluat.w1 import calendar_vn as cal

D = dt.date


def test_add_days_and_count():
    assert cal.add_period(D(2022, 3, 1), 15, "day") == D(2022, 3, 16)
    assert cal.count_days(D(2022, 3, 1), D(2022, 3, 16)) == 15


def test_add_month_clamps_end_of_month():
    assert cal.add_period(D(2022, 1, 31), 1, "month") == D(2022, 2, 28)   # 2022 không nhuận
    assert cal.add_period(D(2024, 1, 31), 1, "month") == D(2024, 2, 29)   # nhuận
    assert cal.add_period(D(2022, 1, 15), 2, "month") == D(2022, 3, 15)


def test_add_year():
    assert cal.add_period(D(2020, 3, 15), 3, "year") == D(2023, 3, 15)
    assert cal.add_period(D(2020, 2, 29), 1, "year") == D(2021, 2, 28)    # kẹp


def test_weekend_and_fixed_holiday_are_rest_days():
    assert cal.is_rest_day(D(2022, 3, 19))                 # thứ 7
    assert cal.is_rest_day(D(2022, 3, 20))                 # CN
    assert cal.is_rest_day(D(2022, 9, 2))                  # Quốc khánh (dương cố định)
    assert cal.is_rest_day(D(2022, 1, 1))                  # Tết dương
    assert not cal.is_rest_day(D(2022, 3, 16))             # thứ 4 thường


def test_next_business_day_rolls_weekend():
    assert cal.next_business_day(D(2022, 3, 19)) == D(2022, 3, 21)   # T7 → T2
    assert cal.next_business_day(D(2022, 3, 16)) == D(2022, 3, 16)   # ngày làm giữ nguyên


def test_next_business_day_skips_holiday_then_weekend():
    # 30/4/2022 là T7 + lễ, 1/5 CN + lễ, 2/5 T2 (nghỉ bù thực tế nhưng built-in chỉ
    # lễ cố định) → built-in: 30/4(lễ),1/5(lễ+CN),2/5 T2 là ngày làm.
    assert cal.next_business_day(D(2022, 4, 30)) == D(2022, 5, 2)


def test_invalid_unit():
    try:
        cal.add_period(D(2022, 1, 1), 1, "week")
    except ValueError:
        return
    raise AssertionError("phải raise ValueError cho unit lạ")
