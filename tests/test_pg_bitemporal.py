"""Integration (Postgres) — reconstruct qua DB + bất biến no-overlap DO DB GÁC.

Skip nếu không nối được Postgres (CI/máy chưa dựng docker-compose).
Mỗi test chạy trong 1 transaction rồi ROLLBACK → DB sạch.
"""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa

from traluat.w2 import repo
from traluat.w2.db import make_engine
from traluat.w2.models import Document, Unit, UnitVersion
from sqlalchemy.orm import Session

D = dt.date
EID = "nd99__dieu_3__khoan_2"


@pytest.fixture()
def session():
    try:
        engine = make_engine()
        conn = engine.connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    s = Session(bind=conn, future=True)
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:        # tx có thể đã abort sau ExclusionViolation
            trans.rollback()       # mọi thứ test ghi đều bị cuốn → DB sạch
        conn.close()


def _seed(s: Session) -> None:
    doc = Document(frbr_uri="trl:vn/nd/99/2020", doc_type="nghi_dinh")
    s.add(doc)
    s.flush()
    s.add(Unit(document_id=doc.id, unit_type="khoan", ordinal=2, label="2", eid=EID))
    s.flush()
    s.add(UnitVersion(
        unit_id=s.scalar(sa.select(Unit.id).where(Unit.eid == EID)),
        lang="vi", valid_from=D(2021, 1, 1), valid_to=None, text="Mức vốn 20 tỷ.",
    ))
    s.flush()


def test_reconstruct_via_db(session: Session):
    _seed(session)
    repo.apply_amendment(session, EID, "Mức vốn 50 tỷ.", D(2023, 6, 1), source_relation_id="r1")

    assert repo.reconstruct_as_of(session, EID, D(2020, 12, 31)) is None
    assert repo.reconstruct_as_of(session, EID, D(2022, 1, 1)) == "Mức vốn 20 tỷ."
    assert repo.reconstruct_as_of(session, EID, D(2023, 6, 1)) == "Mức vốn 50 tỷ."  # biên


def test_idempotent_via_db(session: Session):
    _seed(session)
    repo.apply_amendment(session, EID, "B", D(2023, 6, 1), source_relation_id="r1")
    repo.apply_amendment(session, EID, "B", D(2023, 6, 1), source_relation_id="r1")  # replay
    n = session.scalar(sa.select(sa.func.count()).select_from(UnitVersion))
    assert n == 2  # bản gốc + 1 amendment (không nhân đôi)


def test_exclude_constraint_enforced_by_db(session: Session):
    """★ Bất biến DO POSTGRES GÁC: chèn dòng in-force CHỒNG nhau → ExclusionViolation."""
    _seed(session)
    uid = session.scalar(sa.select(Unit.id).where(Unit.eid == EID))
    # bản gốc [2021-01-01, ∞). Chèn thẳng một bản mở KHÁC phủ 2022 → chồng.
    session.add(UnitVersion(unit_id=uid, lang="vi", valid_from=D(2022, 1, 1), valid_to=None, text="X"))
    with pytest.raises(sa.exc.IntegrityError):  # Postgres uv_no_overlap
        session.flush()
