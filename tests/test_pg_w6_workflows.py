"""End-to-end (Postgres): W6 capability — ComplianceDiff + JudgmentAnalysis."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2 import repo
from traluat.w2.db import make_engine
from traluat.w6 import ComplianceDiffService, JudgmentAnalysisService

D = dt.date
FRBR = "trl:vn/nd/99/2020"
from tests.test_w1_structure import SAMPLE


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    s = Session(bind=conn, future=True)
    load_to_w2(s, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
               units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP")
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def test_compliance_diff_modified_and_removed(session: Session):
    repo.apply_amendment(session, "nd99__dieu_3__khoan_2", "Mức vốn 50 tỷ đồng.",
                         D(2023, 6, 1), source_relation_id="a1")
    repo.repeal(session, "nd99__dieu_5", D(2023, 6, 1))

    diffs = {d.eid: d for d in ComplianceDiffService(session).diff(FRBR, D(2022, 1, 1), D(2024, 1, 1))}
    assert diffs["nd99__dieu_3__khoan_2"].change == "modified"
    assert "20 tỷ" in diffs["nd99__dieu_3__khoan_2"].before
    assert "50 tỷ" in diffs["nd99__dieu_3__khoan_2"].after
    assert diffs["nd99__dieu_5"].change == "removed"      # bãi bỏ → removed


def test_judgment_analysis_flags_only_binding(session: Session):
    svc = JudgmentAnalysisService(session)
    # bản án KHÔNG viện dẫn Điều 3 (còn hiệu lực @2022, đúng tình huống) → cờ
    f = svc.analyze(cited_eids=["nd99__dieu_1"],
                    expected_governing=["nd99__dieu_1", "nd99__dieu_3"], as_of=D(2022, 1, 1))
    assert f.flagged and "nd99__dieu_3" in f.missing_binding

    # viện dẫn đủ → không cờ (không auto 'thẩm phán sai')
    f2 = svc.analyze(cited_eids=["nd99__dieu_1", "nd99__dieu_3"],
                     expected_governing=["nd99__dieu_1", "nd99__dieu_3"], as_of=D(2022, 1, 1))
    assert not f2.flagged
