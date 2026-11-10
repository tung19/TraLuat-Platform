"""End-to-end (Postgres): JurisdictionPack bơm thang bậc → đổi vùng tài phán,
winner xung đột LẬT theo pack (engine không đổi)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2.db import make_engine
from traluat.w3 import find_and_resolve_conflicts
from traluat.w6 import JurisdictionPack

D = dt.date
LUAT, TT = "trl:vn/luat/59/2020", "trl:vn/tt/01/2021"


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    s = Session(bind=conn, future=True)
    load_to_w2(s, frbr_uri=LUAT, doc_type="luat", date_effective=D(2020, 1, 1),
               units=build_ingest("Điều 1. Thời hạn\nThời hạn nộp hồ sơ đăng ký doanh nghiệp là 30 ngày.", "luat59"),
               doc_number="59/2020/QH14")
    load_to_w2(s, frbr_uri=TT, doc_type="thong_tu", date_effective=D(2021, 1, 1),
               units=build_ingest("Điều 1. Thời hạn\nThời hạn nộp hồ sơ đăng ký doanh nghiệp là 15 ngày.", "tt01"),
               doc_number="01/2021/TT-BKHĐT")
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def test_default_pack_luat_wins(session: Session):
    f = find_and_resolve_conflicts(session, [LUAT, TT], D(2022, 1, 1))[0]
    assert f.resolution.winner_eid == "luat59__dieu_1"      # VN: Luật(90) > Thông tư(50)


def test_custom_pack_flips_winner(session: Session):
    # vùng tài phán giả định: 'thong_tu' cao hơn 'luat' → winner LẬT (engine không đổi)
    pack = JurisdictionPack(code="xx", rank_table={"luat": 10, "thong_tu": 90})
    f = find_and_resolve_conflicts(session, [LUAT, TT], D(2022, 1, 1), pack=pack)[0]
    assert f.resolution.winner_eid == "tt01__dieu_1"
