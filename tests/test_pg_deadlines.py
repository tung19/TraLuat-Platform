"""FR-35.13 · thời hiệu/thời hạn tố tụng — reference-data hiệu-lực-aware + neo điều."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

import traluat.w1.deadlines  # noqa: F401  (đăng ký @calculator("thoi_hieu"))
from traluat.w1 import calculators
from traluat.w1.deadlines import compute_deadline
from traluat.w1.reference import RefRow, upsert_reference
from traluat.w2.db import make_engine

D = dt.date


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    if conn.execute(sa.text("select to_regclass('public.reference_value')")).scalar() is None:
        trans.rollback(); conn.close()
        pytest.skip("reference_value chưa migrate")
    s = Session(bind=conn, future=True)
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def _seed(s):
    upsert_reference(s, "thoi_hieu", [
        RefRow("khang_cao_so_tham_ds", {"value": 15, "unit": "day"},
               D(2016, 7, 1), None, "bltts2015__dieu_273"),
        RefRow("khoi_kien_hop_dong", {"value": 3, "unit": "year"},
               D(2017, 1, 1), None, "blds2015__dieu_429"),
    ], pii_check=False)


def test_appeal_15_days_with_source(session: Session):
    _seed(session)
    r = compute_deadline(session, "khang_cao_so_tham_ds", D(2022, 3, 1), D(2022, 6, 1))
    assert r.deadline == D(2022, 3, 16)             # +15 ngày, T4 → không lùi
    assert r.rolled_from is None
    assert r.source_eid == "bltts2015__dieu_273"    # neo điều luật (moat)
    assert r.value == 15 and r.unit == "day"


def test_deadline_rolls_when_landing_on_weekend(session: Session):
    _seed(session)
    r = compute_deadline(session, "khang_cao_so_tham_ds", D(2022, 3, 4), D(2022, 6, 1))
    # 2022-03-04 (T6) + 15 = 2022-03-19 (T7) → lùi sang T2 2022-03-21
    assert r.rolled_from == D(2022, 3, 19)
    assert r.deadline == D(2022, 3, 21)


def test_statute_of_limitations_years(session: Session):
    _seed(session)
    r = compute_deadline(session, "khoi_kien_hop_dong", D(2020, 3, 16), D(2021, 1, 1))
    assert r.deadline == D(2023, 3, 16) and r.unit == "year"


def test_effectivity_aware_period_changes_at_as_of(session: Session):
    # luật tố tụng đổi: từ 2025-01-01 thời hạn kháng cáo giả định đổi 15 → 30 ngày
    upsert_reference(session, "thoi_hieu", [
        RefRow("khang_cao_so_tham_ds", {"value": 15, "unit": "day"},
               D(2016, 7, 1), D(2025, 1, 1), "bltts2015__dieu_273"),
        RefRow("khang_cao_so_tham_ds", {"value": 30, "unit": "day"},
               D(2025, 1, 1), None, "bltts_moi__dieu_X"),
    ], pii_check=False, version="v2")
    old = compute_deadline(session, "khang_cao_so_tham_ds", D(2024, 6, 3), D(2024, 6, 3))
    new = compute_deadline(session, "khang_cao_so_tham_ds", D(2025, 6, 2), D(2025, 6, 2))
    assert old.value == 15 and new.value == 30      # bitemporal: thời hạn@as_of
    assert new.source_eid == "bltts_moi__dieu_X"


def test_holiday_from_reference_rolls_deadline(session: Session):
    _seed(session)
    # nạp ngày lễ âm (vd mùng 1 Tết) rơi đúng ngày hết hạn → lùi qua lễ
    # chọn start sao cho +15 ngày = một ngày THƯỜNG (T4) rồi đánh dấu nó là lễ
    from traluat.w1.reference import RefRow as RR
    upsert_reference(session, "ngay_nghi", [
        RR("2022", {"dates": ["2022-03-16"]}, D(2000, 1, 1), None, None)],
        pii_check=False)
    r = compute_deadline(session, "khang_cao_so_tham_ds", D(2022, 3, 1), D(2022, 6, 1))
    assert r.rolled_from == D(2022, 3, 16)          # ngày lễ (reference) → lùi
    assert r.deadline == D(2022, 3, 17)             # T5 kế tiếp


def test_rollover_across_year_boundary_uses_next_year_holidays(session: Session):
    # F5: hạn rơi cuối năm, lùi sang lễ ÂM năm SAU phải được nạp (không chỉ raw.year).
    from traluat.w1.reference import RefRow as RR
    upsert_reference(session, "thoi_hieu", [
        RR("khieu_nai_lan_dau", {"value": 1, "unit": "day"},
           D(2012, 7, 1), None, "luatkn__dieu_9")], pii_check=False)
    # Tết 2023 (âm) rơi 2023-01-23; mốc 2023-01-22 + 1 ngày = 2023-01-23 (lễ năm sau
    # so với mốc cuối 2022? dùng ngay năm 2023 để chứng minh union năm kế). Ở đây minh
    # hoạ union: đánh dấu 2023-12-31→2024-01-01 là lễ để lùi qua giao thừa dương.
    upsert_reference(session, "ngay_nghi", [
        RR("2023", {"dates": ["2023-12-30"]}, D(2000, 1, 1), None, None),
        RR("2024", {"dates": ["2024-01-01", "2024-01-02"]}, D(2000, 1, 1), None, None)],
        pii_check=False)
    # mốc 2023-12-29 (T6) +1 = 2023-12-30 (T7 + lễ) → lùi: 31(CN) · 01/01(lễ 2024) ·
    # 02/01(lễ 2024) · 03/01(T4) = ngày làm. Cần lễ 2024 (năm sau) mới ra đúng.
    r = compute_deadline(session, "khieu_nai_lan_dau", D(2023, 12, 29), D(2024, 1, 1))
    assert r.rolled_from == D(2023, 12, 30)
    assert r.deadline == D(2024, 1, 3)             # lùi qua lễ năm 2024 (union năm kế)


def test_deadline_auto_rolls_over_tet_without_reference(session: Session):
    # 35.14: lễ Tết TÍNH TỰ ĐỘNG (không cần seed ngay_nghi) → hạn rơi Tết tự lùi.
    from traluat.w1.reference import RefRow as RR
    upsert_reference(session, "thoi_hieu", [
        RR("khieu_nai_lan_dau", {"value": 1, "unit": "day"},
           D(2012, 7, 1), None, "luatkn__dieu_9")], pii_check=False)
    # mốc 2022-01-30 (CN) +1 = 2022-01-31 (30 Chạp, lễ âm) → lùi qua cụm Tết
    # (31/1..4/2) + cuối tuần 5-6/2 → 2022-02-07 (T2). KHÔNG seed lễ nào.
    r = compute_deadline(session, "khieu_nai_lan_dau", D(2022, 1, 30), D(2022, 6, 1))
    assert r.rolled_from == D(2022, 1, 31)
    assert r.deadline == D(2022, 2, 7)


def test_no_data_raises(session: Session):
    with pytest.raises(LookupError):
        compute_deadline(session, "khong_co", D(2022, 1, 1), D(2022, 1, 1))


def test_registered_as_toolbox_calculator(session: Session):
    _seed(session)
    assert "thoi_hieu" in calculators.available()
    res = calculators.run(session, "thoi_hieu",
                          {"kind": "khang_cao_so_tham_ds", "moc_bat_dau": "2022-03-04"},
                          D(2022, 6, 1))
    assert res.value["deadline"] == "2022-03-21" and res.source_eid == "bltts2015__dieu_273"
