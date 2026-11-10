"""End-to-end (Postgres): phased-commencement — mỗi đơn vị lấy valid_from
riêng; override cấp Điều lan xuống con, override cấp Khoản chỉ riêng khoản đó."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from traluat.w1 import ingest_document
from traluat.w2 import repo
from traluat.w2.db import make_engine

D = dt.date
from tests.test_w1_phased import PHASED  # noqa: E402


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


def _at(session, eid, d):
    return repo.reconstruct_as_of(session, eid, d)


def test_phased_valid_from_per_unit(session: Session):
    ingest_document(session, PHASED, "nd20")

    # Khoản 1 Điều 2: KHÔNG override → theo cấp VB (01/3/2022)
    assert _at(session, "nd20__dieu_2__khoan_1", D(2022, 4, 1)) == "Quy định A."

    # Khoản 2 Điều 2: override cấp Khoản 01/7/2022 — chỉ riêng khoản này trễ
    assert _at(session, "nd20__dieu_2__khoan_2", D(2022, 4, 1)) is None
    assert _at(session, "nd20__dieu_2__khoan_2", D(2022, 8, 1)) == "Quy định B."

    # Điều 1 (có nội dung): override cấp Điều 01/6/2022
    assert _at(session, "nd20__dieu_1", D(2022, 4, 1)) is None
    assert "Quy định chung" in _at(session, "nd20__dieu_1", D(2022, 7, 1))

    # Điều 3: override cấp Điều 01/9/2022 LAN xuống Khoản 1 (con)
    assert _at(session, "nd20__dieu_3__khoan_1", D(2022, 8, 1)) is None
    assert _at(session, "nd20__dieu_3__khoan_1", D(2022, 10, 1)) == "Quy định C."
