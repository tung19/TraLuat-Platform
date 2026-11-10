"""FR-39/40 · Danh bạ geo — nearby KNN (PostGIS) + PII quarantine (CCCD).

Cần image Postgres có PostGIS (deploy/postgres) + extra `geo` (geoalchemy2).
Thiếu → skip (nhất quán các test tuỳ-chọn khác).
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

pytest.importorskip("geoalchemy2")

from traluat.w1.directory import (
    DirectoryQuarantined,
    add_directory_entry,
    nearby,
)
from traluat.w2.db import make_engine

# Toạ độ (lat, lon)
HCMC = (10.7769, 106.7009)      # TAND TP.HCM (xấp xỉ)
HCMC2 = (10.7900, 106.6950)     # cách ~1.5 km
HANOI = (21.0278, 105.8342)     # cách ~1140 km


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    if conn.execute(
            sa.text("select to_regclass('public.directory')")).scalar() is None:
        trans.rollback(); conn.close()
        pytest.skip("directory chưa migrate (PostGIS)")
    s = Session(bind=conn, future=True)
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def test_nearby_radius_and_order(session: Session):
    add_directory_entry(session, "toa_an", "TAND TP.HCM",
                        lat=HCMC[0], lon=HCMC[1], province="HCM")
    add_directory_entry(session, "toa_an", "TAND Q.1 (gần)",
                        lat=HCMC2[0], lon=HCMC2[1], province="HCM")
    add_directory_entry(session, "toa_an", "TAND TP.Hà Nội (xa)",
                        lat=HANOI[0], lon=HANOI[1], province="HN")

    hits = nearby(session, HCMC[0], HCMC[1], radius_m=50_000)
    names = [h.entry.name for h in hits]
    assert "TAND TP.HCM" in names and "TAND Q.1 (gần)" in names
    assert "TAND TP.Hà Nội (xa)" not in names          # ngoài 50 km
    assert hits[0].entry.name == "TAND TP.HCM"          # gần nhất trước (distance ~0)
    assert hits[0].distance_m < hits[1].distance_m      # sắp theo khoảng cách


def test_nearby_kind_filter(session: Session):
    add_directory_entry(session, "toa_an", "Toà", lat=HCMC[0], lon=HCMC[1])
    add_directory_entry(session, "cong_chung", "VPCC gần", lat=HCMC2[0], lon=HCMC2[1])
    hits = nearby(session, HCMC[0], HCMC[1], radius_m=50_000, kind="cong_chung")
    assert [h.entry.kind for h in hits] == ["cong_chung"]


def test_business_contact_allowed_but_cccd_quarantined(session: Session):
    # điện thoại/email nghiệp vụ được phép
    row = add_directory_entry(session, "luat_su", "VPLS An Phát",
                              phone="02838221234", email="info@anphat.vn",
                              lat=HCMC[0], lon=HCMC[1])
    assert row.phone == "02838221234"
    # CCCD (12 số) trong tên/địa chỉ → chặn publish danh bạ công
    with pytest.raises(DirectoryQuarantined):
        add_directory_entry(session, "luat_su", "LS Nguyễn Văn A 012345678901",
                            lat=HCMC[0], lon=HCMC[1])


def test_invalid_kind_rejected(session: Session):
    with pytest.raises(ValueError):
        add_directory_entry(session, "khong_hop_le", "X")
