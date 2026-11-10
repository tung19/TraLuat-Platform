"""End-to-end (Postgres): reference-data adapter — PII gate · idempotent · hiệu-lực lookup."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.tools.reference import RefRow, lookup_reference, upsert_reference
from traluat.w2.db import make_engine
from traluat.w2.models import ReferenceValue

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


def _count(s, dataset="muc_phat", key="hanh_vi_x"):
    # ĐẾM THEO KHOÁ (không đếm toàn bảng) → robust với seed-data đã commit; vẫn chứng
    # minh idempotent (re-upsert cùng khoá không nhân đôi).
    return s.scalar(sa.select(sa.func.count()).select_from(ReferenceValue).where(
        ReferenceValue.dataset == dataset, ReferenceValue.key == key))


def test_effectivity_aware_lookup_with_source(session: Session):
    # mức phạt hành vi X đổi theo luật: 5tr [2020,2023) → 10tr [2023,∞), CÓ nguồn điều
    rows = [RefRow("hanh_vi_x", {"muc": 5_000_000}, D(2020, 1, 1), D(2023, 1, 1), "nd99__dieu_3"),
            RefRow("hanh_vi_x", {"muc": 10_000_000}, D(2023, 1, 1), None, "nd50__dieu_1")]
    out = upsert_reference(session, "muc_phat", rows)
    assert out.loaded == 2 and out.quarantined == []

    assert lookup_reference(session, "muc_phat", "hanh_vi_x", D(2022, 1, 1)).value["muc"] == 5_000_000
    v = lookup_reference(session, "muc_phat", "hanh_vi_x", D(2024, 1, 1))
    assert v.value["muc"] == 10_000_000 and v.source_eid == "nd50__dieu_1"   # calculator có-nguồn-luật

    upsert_reference(session, "muc_phat", rows)        # idempotent → không nhân đôi
    assert _count(session) == 2


def test_pii_check_off_for_numeric_dataset(session: Session):
    # A2-fix: dataset SỐ (muc_phat) đặt pii_check=False → số tiền 12 chữ số KHÔNG bị
    # quarantine oan (100 tỷ ≈ CCCD về regex).
    out = upsert_reference(session, "muc_phat",
                           [RefRow("x", {"muc": 100_000_000_000}, D(2020, 1, 1))],
                           pii_check=False)
    assert out.loaded == 1 and out.quarantined == []


def test_pii_gate_quarantines(session: Session):
    out = upsert_reference(session, "danh_ba", [
        RefRow("cb_ok", {"co_quan": "Sở KHĐT Hà Nội"}, D(2020, 1, 1)),
        RefRow("cb_pii", {"phone": "0912345678"}, D(2020, 1, 1)),   # có SĐT → giữ
    ])
    assert out.loaded == 1 and out.quarantined == ["cb_pii"]
    assert lookup_reference(session, "danh_ba", "cb_pii", D(2022, 1, 1)) is None
