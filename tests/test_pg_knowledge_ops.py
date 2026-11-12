"""End-to-end (Postgres): L14 HITL — duyệt quan hệ mở cổng materialize + gold export."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from traluat.core.eval_harness import GoldCase, load_gold
from traluat.core.knowledge_ops import append_gold, approve_relation, pending_relations
from traluat.w1 import build_ingest, extract_and_load_relations, load_to_w2
from traluat.w2 import repo
from traluat.w2.db import make_engine

D = dt.date
from tests.test_w1_structure import SAMPLE

ND50 = "Điều 1. Bãi bỏ Điều 5 của Nghị định số 99/2020/NĐ-CP kể từ ngày 01/6/2023."


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    s = Session(bind=conn, future=True)
    load_to_w2(s, frbr_uri="trl:vn/nd/99/2020", doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
               units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP")
    load_to_w2(s, frbr_uri="trl:vn/nd/50/2023", doc_type="nghi_dinh", date_effective=D(2023, 6, 1),
               units=build_ingest(ND50, "nd50"), doc_number="50/2023/NĐ-CP")
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def test_hitl_approve_opens_materialize(session: Session):
    created, _ = extract_and_load_relations(session, src_frbr_uri="trl:vn/nd/50/2023", text=ND50)
    (rel,) = created

    queue = pending_relations(session)
    assert rel.id in {r.id for r in queue}             # hàng đợi HITL có nó

    # trước duyệt: gate chặn, Điều 5 còn hiệu lực 2024
    assert repo.materialize(session, rel) is False
    assert repo.reconstruct_as_of(session, "nd99__dieu_5", D(2024, 1, 1)) is not None

    approve_relation(session, rel.id)                  # chuyên gia duyệt
    assert repo.materialize(session, rel) is True      # cổng mở → áp
    assert repo.reconstruct_as_of(session, "nd99__dieu_5", D(2024, 1, 1)) is None   # bị bãi bỏ


def test_append_gold_roundtrip(tmp_path: Path):
    f = tmp_path / "gold.jsonl"
    append_gold(f, GoldCase("c1", "vốn pháp định", D(2022, 1, 1),
                            gold_eids=["nd99__dieu_3__khoan_2"], tags=["correct-article"]))
    cases = load_gold(f)
    assert len(cases) == 1 and cases[0].gold_eids == ["nd99__dieu_3__khoan_2"]
