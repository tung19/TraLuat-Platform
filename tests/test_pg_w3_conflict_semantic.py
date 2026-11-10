"""End-to-end (Postgres): SemanticConflictDetector port — bắt mâu thuẫn KHÔNG số
mà detector số bỏ qua, rồi giải bằng resolve_conflict."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2.db import make_engine
from traluat.w3 import ConflictCandidate, detect_conflicts, find_and_resolve_conflicts

D = dt.date
LUAT, TT = "trl:vn/luat/59/2020", "trl:vn/tt/01/2021"
# cùng chủ đề 'chuyển nhượng', KHÔNG số → detector số không bắt
LUAT_TXT = "Điều 1. Chuyển nhượng\nViệc chuyển nhượng phần vốn góp được phép thực hiện."
TT_TXT = "Điều 1. Chuyển nhượng\nViệc chuyển nhượng phần vốn góp bị cấm thực hiện."


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    s = Session(bind=conn, future=True)
    load_to_w2(s, frbr_uri=LUAT, doc_type="luat", date_effective=D(2020, 1, 1),
               units=build_ingest(LUAT_TXT, "luat59"), doc_number="59/2020/QH14")
    load_to_w2(s, frbr_uri=TT, doc_type="thong_tu", date_effective=D(2021, 1, 1),
               units=build_ingest(TT_TXT, "tt01"), doc_number="01/2021/TT-BKHĐT")
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


class _FakeSemantic:
    """Flag cặp 'được phép' vs 'bị cấm' (không số)."""
    def detect(self, pairs):
        out = []
        for a, ta, b, tb in pairs:
            if ("phép" in ta and "cấm" in tb) or ("cấm" in ta and "phép" in tb):
                out.append(ConflictCandidate(a, b, "semantic", "cho phép vs cấm"))
        return out


def test_numeric_detector_misses_semantic(session: Session):
    assert detect_conflicts(session, [LUAT, TT], D(2022, 1, 1)) == []   # không số → bỏ qua


def test_semantic_port_catches_and_resolves(session: Session):
    findings = find_and_resolve_conflicts(session, [LUAT, TT], D(2022, 1, 1),
                                          semantic=_FakeSemantic())
    assert len(findings) == 1
    assert findings[0].candidate.kind == "semantic"
    assert findings[0].resolution.winner_eid == "luat59__dieu_1"   # Luật > Thông tư
