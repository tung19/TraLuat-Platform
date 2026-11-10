"""FR-35 calculators — RULE tier, hiệu-lực + có-nguồn-luật."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w1.calculators import available, run
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


def test_registry_has_calcs():
    assert {"muc_phat", "thue_tncn", "luong_toi_thieu"} <= set(available())


def test_muc_phat_effectivity_with_source(session: Session):
    # mức phạt đổi theo luật: 5tr [2020,2023) nguồn nd99; 10tr [2023,∞) nguồn nd50
    upsert_reference(session, "muc_phat", [
        RefRow("vuot_den_do", {"muc": 5_000_000}, D(2020, 1, 1), D(2023, 1, 1), "nd99__dieu_3"),
        RefRow("vuot_den_do", {"muc": 10_000_000}, D(2023, 1, 1), None, "nd50__dieu_1"),
    ], pii_check=False)

    r22 = run(session, "muc_phat", {"hanh_vi": "vuot_den_do"}, D(2022, 1, 1))
    assert r22.value["muc"] == 5_000_000 and r22.source_eid == "nd99__dieu_3"   # có-nguồn-luật
    r24 = run(session, "muc_phat", {"hanh_vi": "vuot_den_do"}, D(2024, 1, 1))
    assert r24.value["muc"] == 10_000_000 and r24.source_eid == "nd50__dieu_1"  # @ngày khác


def test_thue_tncn_computes(session: Session):
    upsert_reference(session, "thue_suat_tncn", [
        RefRow("bac1", {"rate": 0.05}, D(2020, 1, 1), None, "luat_tncn__dieu_22")], pii_check=False)
    r = run(session, "thue_tncn", {"thu_nhap": 10_000_000, "bac": "bac1"}, D(2022, 1, 1))
    assert r.value["thue"] == 500_000 and r.source_eid == "luat_tncn__dieu_22"
