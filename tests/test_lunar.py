"""FR-35.14 · âm lịch VN — chuyển đổi dương↔âm (thuần, không DB)."""

from __future__ import annotations

import datetime as dt

from traluat.tools import calendar_vn as cal
from traluat.tools.lunar import gio_to_date, lunar_to_solar, solar_to_lunar, tet_date

D = dt.date


def test_tet_dates_known():
    assert tet_date(2022) == D(2022, 2, 1)
    assert tet_date(2023) == D(2023, 1, 22)
    assert tet_date(2024) == D(2024, 2, 10)
    assert tet_date(2025) == D(2025, 1, 29)


def test_gio_to_known():
    assert gio_to_date(2022) == D(2022, 4, 10)    # 10/3 âm
    assert gio_to_date(2024) == D(2024, 4, 18)


def test_roundtrip_solar_lunar():
    for d in (D(2022, 2, 1), D(2023, 9, 10), D(2024, 12, 31)):
        ld, lm, ly, leap = solar_to_lunar(d)
        assert lunar_to_solar(ld, lm, ly, leap) == d


def test_vn_lunar_holidays_contains_tet_and_gio():
    h = cal.vn_lunar_holidays(2022)
    assert D(2022, 2, 1) in h and D(2022, 2, 2) in h        # mùng 1,2 Tết
    assert D(2022, 4, 10) in h                              # Giỗ Tổ
