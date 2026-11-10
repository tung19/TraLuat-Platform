"""End-to-end (Postgres): FR-41 — phát hiện mâu thuẫn số xuyên văn bản rồi giải
bằng lex superior (Luật > Thông tư)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2.db import make_engine
from traluat.w3 import detect_conflicts, find_and_resolve_conflicts

D = dt.date
LUAT = "trl:vn/luat/59/2020"
TT = "trl:vn/tt/01/2021"

LUAT_TXT = "Điều 1. Thời hạn\nThời hạn nộp hồ sơ đăng ký doanh nghiệp là 30 ngày làm việc."
TT_TXT = "Điều 1. Thời hạn\nThời hạn nộp hồ sơ đăng ký doanh nghiệp là 15 ngày làm việc."


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    s = Session(bind=conn, future=True)
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def _seed(session: Session, tt_text: str = TT_TXT) -> None:
    load_to_w2(session, frbr_uri=LUAT, doc_type="luat", date_effective=D(2020, 1, 1),
               units=build_ingest(LUAT_TXT, "luat59"), doc_number="59/2020/QH14")
    load_to_w2(session, frbr_uri=TT, doc_type="thong_tu", date_effective=D(2021, 1, 1),
               units=build_ingest(tt_text, "tt01"), doc_number="01/2021/TT-BKHĐT")


def test_detect_and_resolve_numeric_conflict(session: Session):
    _seed(session)
    findings = find_and_resolve_conflicts(session, [LUAT, TT], D(2022, 1, 1))

    assert len(findings) == 1
    f = findings[0]
    assert f.candidate.kind == "numeric_divergence"
    assert "ngày" in f.candidate.evidence           # 30 vs 15
    # lex superior: Luật (90) thắng Thông tư (50)
    assert f.resolution.winner_eid == "luat59__dieu_1"
    assert f.resolution.rule == "lex_superior"


def test_no_conflict_when_numbers_agree(session: Session):
    # Thông tư cùng số 30 ngày → KHÔNG mâu thuẫn
    _seed(session, tt_text="Điều 1. Thời hạn\nThời hạn nộp hồ sơ đăng ký doanh nghiệp là 30 ngày làm việc.")
    assert detect_conflicts(session, [LUAT, TT], D(2022, 1, 1)) == []


def test_b2_overlapping_values_not_flagged(session: Session):
    # Luật {30}, Thông tư {15,30} (liệt kê cả hai) → GIAO nhau → KHÔNG xung đột (B2-fix)
    _seed(session, tt_text="Điều 1. Thời hạn\nThời hạn nộp hồ sơ đăng ký doanh nghiệp là 15 hoặc 30 ngày làm việc.")
    assert detect_conflicts(session, [LUAT, TT], D(2022, 1, 1)) == []
