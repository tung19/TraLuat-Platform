"""FR-35 calculators — RULE tier, hiệu-lực + có-nguồn-luật."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from tests.reference_helpers import seed_reference_sources
from traluat.tools.calculators import available, run
from traluat.tools.reference import RefRow, upsert_reference
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
    seed_reference_sources(s, ['nd99__dieu_3', 'nd50__dieu_1', 'luat_tncn__dieu_22', 'luat_gtgt__dieu_8', 'bllĐ2019__dieu_98', 'luat_bhxh__dieu_85', 'nq954_2020', 'luat_tncn_cu', 'nd_atiga', 'luat_bhxh__dieu_60'])
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


def test_thue_gtgt(session: Session):
    upsert_reference(session, "thue_gtgt", [
        RefRow("chung_10", {"rate": 0.10}, D(2020, 1, 1), None, "luat_gtgt__dieu_8")],
        pii_check=False)
    r = run(session, "thue_gtgt", {"gia": 1_000_000, "loai": "chung_10"}, D(2022, 1, 1))
    assert r.value["thue"] == 100_000 and r.value["gia_sau_thue"] == 1_100_000
    assert r.source_eid == "luat_gtgt__dieu_8"


def test_lam_them_gio_rate_by_loai_ngay(session: Session):
    upsert_reference(session, "lam_them_rate", [
        RefRow("ngay_thuong", {"rate": 1.5}, D(2021, 1, 1), None, "bllĐ2019__dieu_98"),
        RefRow("ngay_le", {"rate": 3.0}, D(2021, 1, 1), None, "bllĐ2019__dieu_98"),
    ], pii_check=False)
    r = run(session, "lam_them_gio",
            {"luong_gio": 50_000, "so_gio": 4, "loai_ngay": "ngay_le"}, D(2022, 1, 1))
    assert r.value["tien"] == 600_000 and r.value["he_so"] == 3.0   # 50k×3×4


def _seed_payroll(session):
    # BH + biểu thuế phủ từ 2013 (chỉ giảm-trừ đổi mốc 2020) → test bitemporal gọn
    upsert_reference(session, "ty_le_bh", [
        RefRow("nld", {"rate": 0.105}, D(2013, 1, 1), None, "luat_bhxh__dieu_85")],  # 8+1.5+1%
        pii_check=False)
    upsert_reference(session, "giam_tru_gia_canh", [
        RefRow("chuan", {"ban_than": 11_000_000, "phu_thuoc": 4_400_000},
               D(2020, 7, 1), None, "nq954_2020")], pii_check=False)
    upsert_reference(session, "bieu_thue_tncn", [
        RefRow("thang", {"brackets": [[5_000_000, 0.05], [10_000_000, 0.10],
                                      [18_000_000, 0.15], [32_000_000, 0.20],
                                      [52_000_000, 0.25], [80_000_000, 0.30],
                                      [None, 0.35]]},
               D(2013, 1, 1), None, "luat_tncn__dieu_22")], pii_check=False)


def test_gross_net_progressive_with_source(session: Session):
    _seed_payroll(session)
    # gross 30tr, 1 người phụ thuộc:
    #  BH = 30tr×10.5% = 3,150,000
    #  giảm trừ = 11tr + 4.4tr = 15,400,000
    #  thu nhập tính thuế = 30tr - 3.15tr - 15.4tr = 11,450,000
    #  thuế luỹ tiến: 5tr×5% + 5tr×10% + 1.45tr×15% = 250k+500k+217.5k = 967,500
    #  net = 30tr - 3.15tr - 967,500 = 25,882,500
    r = run(session, "gross_net", {"gross": 30_000_000, "nguoi_phu_thuoc": 1}, D(2022, 1, 1))
    assert r.value["bao_hiem"] == 3_150_000
    assert r.value["thu_nhap_tinh_thue"] == 11_450_000
    assert r.value["thue_tncn"] == 967_500
    assert r.value["net"] == 25_882_500
    assert r.source_eid == "luat_tncn__dieu_22"            # neo biểu thuế (moat)


def test_gross_net_effectivity_aware(session: Session):
    # giảm trừ gia cảnh đổi theo thời điểm → net đổi theo as_of (bitemporal)
    _seed_payroll(session)
    upsert_reference(session, "giam_tru_gia_canh", [
        RefRow("chuan", {"ban_than": 9_000_000, "phu_thuoc": 3_600_000},
               D(2013, 7, 1), D(2020, 7, 1), "luat_tncn_cu")], pii_check=False, version="old")
    old = run(session, "gross_net", {"gross": 20_000_000}, D(2019, 1, 1))  # giảm trừ 9tr
    new = run(session, "gross_net", {"gross": 20_000_000}, D(2022, 1, 1))  # giảm trừ 11tr
    assert new.value["thue_tncn"] < old.value["thue_tncn"]   # giảm trừ cao hơn → thuế thấp hơn


def test_new_calcs_registered():
    assert {"thue_gtgt", "lam_them_gio", "gross_net"} <= set(available())
    assert {"tra_mst", "bieu_thue_xnk", "lich_nop_thue", "tra_nganh",
            "bhxh_mot_lan"} <= set(available())


def test_lookup_calcs(session: Session):
    upsert_reference(session, "ma_so_thue", [
        RefRow("0101243150", {"ten": "Cty A", "trang_thai": "dang_hoat_dong"},
               D(2020, 1, 1), None, None)], pii_check=False)
    r = run(session, "tra_mst", {"mst": "0101243150"}, D(2022, 1, 1))
    assert r.value["trang_thai"] == "dang_hoat_dong"

    upsert_reference(session, "bieu_thue_xnk", [
        RefRow("8703:atiga", {"rate": 0.0}, D(2020, 1, 1), None, "nd_atiga")], pii_check=False)
    r = run(session, "bieu_thue_xnk", {"ma_hs": "8703", "hiep_dinh": "atiga"}, D(2022, 1, 1))
    assert r.value["rate"] == 0.0 and r.source_eid == "nd_atiga"


def test_bhxh_mot_lan_formula(session: Session):
    upsert_reference(session, "bhxh_he_so", [
        RefRow("muc_huong", {"truoc_2014": 1.5, "tu_2014": 2.0},
               D(2016, 1, 1), None, "luat_bhxh__dieu_60")], pii_check=False)
    # bình quân 6tr; 2 năm trước 2014 (×1.5) + 5 năm từ 2014 (×2.0) = 3 + 10 = 13 tháng
    r = run(session, "bhxh_mot_lan",
            {"binh_quan": 6_000_000, "nam_truoc_2014": 2, "nam_tu_2014": 5}, D(2022, 1, 1))
    assert r.value["so_thang"] == 13.0 and r.value["muc_huong"] == 78_000_000
    assert r.source_eid == "luat_bhxh__dieu_60"
