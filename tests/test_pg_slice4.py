"""Integration (Postgres) slice-4 — effect_status · R5 tx-time · multihop graph."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w2 import repo
from traluat.w2.bitemporal import EffectStatus
from traluat.w2.db import make_engine
from traluat.w2.models import Document, NormRelation, Unit, UnitVersion

D = dt.date
UTC = dt.timezone.utc


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


def _doc(s, frbr, eids):
    d = Document(frbr_uri=frbr, doc_type="nghi_dinh")
    s.add(d); s.flush()
    for i, e in enumerate(eids, 1):
        s.add(Unit(document_id=d.id, unit_type="dieu", ordinal=i, label=str(i), eid=e))
    s.flush()
    return d


def test_effect_status_via_db(session):
    _doc(session, "trl:vn/nd/s4a", ["e1"])
    session.add(UnitVersion(unit_id=session.scalar(sa.select(Unit.id).where(Unit.eid == "e1")),
                            lang="vi", valid_from=D(2021, 1, 1), valid_to=None, text="A"))
    session.flush()
    assert repo.effect_status(session, "e1", D(2020, 1, 1)) is EffectStatus.NOT_YET
    assert repo.effect_status(session, "e1", D(2022, 1, 1)) is EffectStatus.IN_FORCE
    assert repo.effect_status(session, "khong_co", D(2022, 1, 1)) is EffectStatus.ABSENT
    repo.repeal(session, "e1", D(2024, 1, 1), source_relation_id="rp")
    assert repo.effect_status(session, "e1", D(2025, 1, 1)) is EffectStatus.EXPIRED_CITABLE


def test_R5_txtime_timetravel(session):
    """Nhập sai valid_from=2021 (đúng là 2020). Sửa R5 → biết 'điều từng tin'."""
    _doc(session, "trl:vn/nd/s4b", ["e2"])
    uid = session.scalar(sa.select(Unit.id).where(Unit.eid == "e2"))
    t0 = dt.datetime(2025, 1, 1, tzinfo=UTC)          # lúc nhập (tin cũ)
    v = UnitVersion(unit_id=uid, lang="vi", valid_from=D(2021, 1, 1), valid_to=None,
                    text="X", tx_from=t0)
    session.add(v); session.flush()

    t_mid = dt.datetime(2025, 6, 1, tzinfo=UTC)        # giữa: vẫn tin bản sai
    assert repo.reconstruct_as_of(session, "e2", D(2020, 6, 1), known_as_of=t_mid) is None

    t1 = dt.datetime(2025, 12, 1, tzinfo=UTC)          # sửa lúc t1
    repo.correct_valid_from(session, v.id, D(2020, 1, 1), now=t1)

    # biết tại t_mid (trước sửa): bản sai [2021,∞) → 2020-06 chưa in-force
    assert repo.reconstruct_as_of(session, "e2", D(2020, 6, 1), known_as_of=t_mid) is None
    # biết HIỆN TẠI: bản đúng [2020,∞) → 2020-06 có hiệu lực
    assert repo.reconstruct_as_of(session, "e2", D(2020, 6, 1)) == "X"


def test_multihop_cycle_and_asof(session):
    d = _doc(session, "trl:vn/nd/s4c", ["a", "b", "c", "dd"])
    ids = {e: session.scalar(sa.select(Unit.id).where(Unit.eid == e)) for e in ("a", "b", "c", "dd")}

    def rel(src, dst, rtype, eff):
        session.add(NormRelation(relation_type=rtype, effective_date=eff,
                                 src_doc_id=d.id, src_unit_id=ids[src],
                                 dst_doc_id=d.id, dst_unit_id=ids[dst],
                                 review_status="approved"))

    rel("a", "b", "amends", D(2020, 1, 1))
    rel("b", "c", "guides", D(2021, 1, 1))
    rel("c", "a", "cites", D(2021, 1, 1))     # chu trình → không loop vô hạn
    rel("a", "dd", "amends", D(2030, 1, 1))    # tương lai → bị as_of lọc
    session.flush()

    got = repo.multihop(session, "a", ["amends", "guides"], max_hops=3, as_of=D(2025, 1, 1))
    assert got == ["b", "c"]      # a→b→c; KHÔNG dd (future), cites không nằm trong rel_types
