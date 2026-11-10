"""End-to-end W1 stage-5 (Postgres): text → cue-phrase → norm_relation
(needs_review) → materialize gate → kho bitemporal đổi 'văn bản tại ngày T'."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, extract_and_load_relations, load_to_w2
from traluat.w2 import repo
from traluat.w2.db import make_engine

D = dt.date
from tests.test_w1_structure import SAMPLE  # noqa: E402


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


# VB sửa đổi: bãi bỏ Điều 5 của ND 99/2020 kể từ 01/6/2023.
ND50 = "Điều 1. Bãi bỏ Điều 5 của Nghị định số 99/2020/NĐ-CP kể từ ngày 01/6/2023."


def _seed_nd99(session: Session) -> None:
    load_to_w2(
        session, frbr_uri="trl:vn/nd/99/2020", doc_type="nghi_dinh",
        date_effective=D(2021, 1, 1), units=build_ingest(SAMPLE, "nd99"),
        doc_number="99/2020/NĐ-CP",
    )


def _seed_nd50(session: Session) -> None:
    load_to_w2(
        session, frbr_uri="trl:vn/nd/50/2023", doc_type="nghi_dinh",
        date_effective=D(2023, 6, 1), units=build_ingest(ND50, "nd50"),
        doc_number="50/2023/NĐ-CP",
    )


def test_cuephrase_relation_blocked_until_approved(session: Session):
    _seed_nd99(session)
    _seed_nd50(session)

    created, unresolved = extract_and_load_relations(
        session, src_frbr_uri="trl:vn/nd/50/2023", text=ND50,
    )
    assert unresolved == []
    (rel,) = created
    assert rel.relation_type == "repeals"
    assert rel.review_status == "needs_review"        # C1: vào hàng đợi duyệt
    assert rel.effective_date == D(2023, 6, 1)
    assert rel.dst_unit_id is not None                # giải đúng Điều 5 của ND 99

    # GATE CHẶN: chưa duyệt → không chạm kho; Điều 5 vẫn còn hiệu lực 2024
    assert repo.materialize(session, rel) is False
    assert repo.reconstruct_as_of(session, "nd99__dieu_5", D(2024, 1, 1)) is not None

    # DUYỆT → materialize → Điều 5 hết hiệu lực từ 01/6/2023
    rel.review_status = "approved"
    session.flush()
    assert repo.materialize(session, rel) is True
    assert repo.reconstruct_as_of(session, "nd99__dieu_5", D(2023, 1, 1)) is not None  # trước mốc
    assert repo.reconstruct_as_of(session, "nd99__dieu_5", D(2024, 1, 1)) is None       # sau mốc


def test_unresolved_when_target_not_ingested(session: Session):
    # chỉ có VB sửa đổi, chưa ingest ND 99 → đích không giải được, KHÔNG bịa FK
    _seed_nd50(session)
    created, unresolved = extract_and_load_relations(
        session, src_frbr_uri="trl:vn/nd/50/2023", text=ND50,
    )
    assert created == []
    assert len(unresolved) == 1 and unresolved[0].dst_doc_number == "99/2020/NĐ-CP"
