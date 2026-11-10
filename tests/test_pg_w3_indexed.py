"""End-to-end (Postgres): L4 index — reindex + retrieve_indexed push-down + BM25.
Cần pgvector (image pgvector/pgvector:pg16). Skip nếu extension/bảng vắng."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2 import repo
from traluat.w2.bitemporal import EffectStatus
from traluat.w2.db import make_engine
from traluat.w2.models import Chunk
from traluat.w3 import reindex_document, retrieve_indexed

D = dt.date
FRBR = "trl:vn/nd/99/2020"
from tests.test_w1_structure import SAMPLE  # noqa: E402


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    if conn.execute(sa.text("select to_regclass('public.chunk')")).scalar() is None:
        trans.rollback()
        conn.close()
        pytest.skip("bảng chunk chưa migrate (alembic upgrade head)")
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


def _count(s):
    return s.scalar(sa.select(sa.func.count()).select_from(Chunk))


def test_reindex_idempotent_and_bm25_pushdown(session: Session):
    n1 = reindex_document(session, FRBR)
    assert n1 > 0 and _count(session) == n1
    reindex_document(session, FRBR)                 # lần 2 → upsert, KHÔNG nhân đôi
    assert _count(session) == n1

    # BM25 push-down (không cần model): 'vốn pháp định' → khoản 2
    res = retrieve_indexed(session, "vốn pháp định tối thiểu", D(2022, 1, 1))
    eids = {r.unit_eid for r in res}
    assert "nd99__dieu_3__khoan_2" in eids
    assert next(r for r in res if r.unit_eid == "nd99__dieu_3__khoan_2").applicable


def test_pushdown_asof_marks_expired(session: Session):
    repo.repeal(session, "nd99__dieu_5", D(2023, 6, 1))
    reindex_document(session, FRBR)
    q = "cơ quan đăng ký kinh doanh thẩm quyền"

    at22 = {r.unit_eid: r for r in retrieve_indexed(session, q, D(2022, 1, 1))}
    assert at22["nd99__dieu_5"].effect_status == EffectStatus.IN_FORCE

    at24 = {r.unit_eid: r for r in retrieve_indexed(session, q, D(2024, 1, 1))}
    # keep-and-mark: vẫn trả nhưng đánh dấu hết hiệu lực (không drop cứng)
    assert at24["nd99__dieu_5"].effect_status == EffectStatus.EXPIRED_CITABLE
    assert not at24["nd99__dieu_5"].applicable


def test_reindex_no_stale_after_tx_correction(session: Session):
    # review-fix: R5 tx-correction đổi version → reindex KHÔNG để lại chunk cũ (stale)
    from traluat.w2.models import Unit, UnitVersion
    reindex_document(session, FRBR)
    vid = session.scalar(sa.select(UnitVersion.id).join(Unit)
                         .where(Unit.eid == "nd99__dieu_3__khoan_1", UnitVersion.tx_to.is_(None)))
    repo.correct_valid_from(session, vid, D(2021, 6, 1))
    reindex_document(session, FRBR)
    svs = session.execute(sa.text(
        "select source_version from chunk where eid='nd99__dieu_3__khoan_1'")).all()
    assert [r[0] for r in svs] == ["2021-06-01"]        # chỉ bản hiện hành, không stale


def test_namespace_isolation(session: Session):
    reindex_document(session, FRBR, namespace="tenant:t1")   # index vào namespace khách
    q = "vốn pháp định tối thiểu"
    assert retrieve_indexed(session, q, D(2022, 1, 1), namespaces=("kb",)) == []      # không rò
    assert retrieve_indexed(session, q, D(2022, 1, 1), namespaces=("tenant:t1",))     # thấy
