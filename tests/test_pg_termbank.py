"""FR-04 termbank — VN-EN-ZH neo điều."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.tools.termbank import add_term, lookup_term
from traluat.w2.db import make_engine

D = dt.date


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    if conn.execute(sa.text("select to_regclass('public.reference_value')")).scalar() is None:
        trans.rollback(); conn.close()
        pytest.skip("reference_value chưa migrate")
    s = Session(bind=conn, future=True)
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def test_termbank_trilingual(session: Session):
    add_term(session, "vốn pháp định", en="legal capital", zh="法定资本",
             source_eid="nd99__dieu_3")
    assert lookup_term(session, "vốn pháp định", D(2022, 1, 1), "en") == "legal capital"
    assert lookup_term(session, "vốn pháp định", D(2022, 1, 1), "zh") == "法定资本"
    assert lookup_term(session, "không có", D(2022, 1, 1)) is None
