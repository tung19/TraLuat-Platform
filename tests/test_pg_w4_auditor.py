"""End-to-end (Postgres): Auditor hard-gate — 3 cổng + element-wise + prune,
chạy trên bitemporal W2 thật. Acceptance W4 §7.1–4."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2 import repo
from traluat.w2.db import make_engine
from traluat.w4 import Article, Auditor, KeywordElementJudge, Precedent

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
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


class CountingJudge:
    def __init__(self) -> None:
        self.calls = 0
        self._inner = KeywordElementJudge()

    def judge(self, element, law_text, party_facts):
        self.calls += 1
        return self._inner.judge(element, law_text, party_facts)


def _seed(session: Session) -> None:
    load_to_w2(session, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
               units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP")


def test_element_wise_not_holistic(session: Session):
    _seed(session)
    art = Article("nd99__dieu_3__khoan_1", elements=[
        "doanh nghiệp nộp hồ sơ",                 # thoả
        "trong thời hạn mười lăm ngày",           # thoả (khớp 'thời hạn')
        "qua cổng dịch vụ công trực tuyến",       # KHÔNG thoả
    ])
    facts = "Doanh nghiệp đã nộp hồ sơ trong thời hạn quy định."
    res = Auditor(session).audit(facts, D(2022, 1, 1), [art])

    assert res.verified_articles == []            # 2/3 thoả → điều KHÔNG áp dụng
    (entry,) = res.trail
    assert entry.gate == 2 and entry.reason == "not_applicable"
    assert "qua cổng dịch vụ công trực tuyến" in entry.detail  # chỉ rõ yếu tố thiếu


def test_effectivity_gate_skips_llm_when_expired(session: Session):
    _seed(session)
    repo.repeal(session, "nd99__dieu_5", D(2023, 6, 1))
    facts = "cơ quan đăng ký kinh doanh có thẩm quyền"

    j24 = CountingJudge()
    r24 = Auditor(session, j24).audit(
        facts, D(2024, 1, 1), [Article("nd99__dieu_5", elements=["cơ quan đăng ký"])])
    assert r24.verified_articles == []
    assert r24.trail[0].reason == "temporally_invalid"
    assert j24.calls == 0                          # cổng 3 loại trước → KHÔNG tốn lời gọi

    j22 = CountingJudge()
    r22 = Auditor(session, j22).audit(
        facts, D(2022, 1, 1), [Article("nd99__dieu_5", elements=["cơ quan đăng ký"])])
    assert [a.unit_eid for a in r22.verified_articles] == ["nd99__dieu_5"]
    assert j22.calls >= 1                           # còn hiệu lực → mới chạy element-wise


def test_prune_precedent_without_live_anchor(session: Session):
    _seed(session)
    repo.repeal(session, "nd99__dieu_5", D(2023, 6, 1))
    prec = Precedent("AL01", cited_unit_eids=["nd99__dieu_5"])

    r24 = Auditor(session).audit("x", D(2024, 1, 1), [Article("nd99__dieu_5")], [prec])
    assert r24.verified_precedents == []           # điểm tựa hết hiệu lực → bỏ án lệ

    r22 = Auditor(session).audit("x", D(2022, 1, 1), [Article("nd99__dieu_5")], [prec])
    assert [p.precedent_id for p in r22.verified_precedents] == ["AL01"]


def test_narrowing_version_mismatch_and_ghost(session: Session):
    _seed(session)
    cands = [
        Article("nd99__dieu_3__khoan_1"),                       # tốt → verified
        Article("nd99__dieu_3__khoan_2", text="NỘI DUNG SAI"),  # sai version → loại
        Article("nd99__dieu_999"),                              # không tồn tại → loại
    ]
    res = Auditor(session).audit("doanh nghiệp nộp hồ sơ", D(2022, 1, 1), cands)

    veids = {a.unit_eid for a in res.verified_articles}
    assert veids == {"nd99__dieu_3__khoan_1"}      # verified ⊆ candidate, điều độc bị loại
    reasons = {e.unit_eid: e.reason for e in res.trail if not e.accepted}
    assert reasons["nd99__dieu_3__khoan_2"] == "version_mismatch"
    assert reasons["nd99__dieu_999"] == "citation_unreachable"
