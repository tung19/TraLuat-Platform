"""Integration (Postgres) — resolve_conflict (§4): lex superior/posterior + gate + abstain."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w2 import repo
from traluat.w2.db import make_engine
from traluat.w2.models import Document, Unit, UnitVersion

D = dt.date
AS_OF = D(2022, 1, 1)


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


_n = 0


def _unit(s, doc_type, eid, *, date_effective, valid_from=D(2021, 1, 1), valid_to=None, text="x"):
    global _n
    _n += 1
    d = Document(frbr_uri=f"trl:vn/{eid}/{_n}", doc_type=doc_type, date_effective=date_effective)
    s.add(d); s.flush()
    s.add(Unit(document_id=d.id, unit_type="dieu", ordinal=1, label="Điều 1", eid=eid))
    s.flush()
    s.add(UnitVersion(unit_id=s.scalar(sa.select(Unit.id).where(Unit.eid == eid)),
                      lang="vi", valid_from=valid_from, valid_to=valid_to, text=text))
    s.flush()


def test_lex_superior(session):
    _unit(session, "luat", "luat_a", date_effective=D(2020, 1, 1))
    _unit(session, "nghi_dinh", "nd_b", date_effective=D(2021, 1, 1))
    r = repo.resolve_conflict(session, ["luat_a", "nd_b"], AS_OF)
    assert r.rule == "lex_superior" and r.winner_eid == "luat_a" and not r.unresolved


def test_effectivity_gate_expired_cannot_win(session):
    # Luật hiệu lực cao HƠN nhưng đã HẾT hiệu lực @2022 → KHÔNG thắng; NĐ in-force thắng.
    _unit(session, "luat", "luat_old", date_effective=D(2015, 1, 1),
          valid_from=D(2015, 1, 1), valid_to=D(2020, 1, 1))  # expired trước 2022
    _unit(session, "nghi_dinh", "nd_live", date_effective=D(2021, 1, 1))
    r = repo.resolve_conflict(session, ["luat_old", "nd_live"], AS_OF)
    assert r.winner_eid == "nd_live"
    assert ("luat_old", "expired_citable") in r.losers  # vẫn được cite kèm status


def test_lex_posterior(session):
    _unit(session, "nghi_dinh", "nd_2020", date_effective=D(2020, 1, 1))
    _unit(session, "nghi_dinh", "nd_2021", date_effective=D(2021, 6, 1))
    r = repo.resolve_conflict(session, ["nd_2020", "nd_2021"], AS_OF)
    assert r.rule == "lex_posterior" and r.winner_eid == "nd_2021"


def test_abstain_ambiguous_rank(session):
    # quyet_dinh (mơ hồ cơ quan) → rank None → ABSTAIN→human
    _unit(session, "quyet_dinh", "qd_x", date_effective=D(2021, 1, 1))
    _unit(session, "nghi_dinh", "nd_y", date_effective=D(2021, 1, 1))
    r = repo.resolve_conflict(session, ["qd_x", "nd_y"], AS_OF)
    assert r.unresolved and r.rule == "abstain:rank_undetermined"


def test_abstain_tie(session):
    # cùng rank + CÙNG ngày → không phân định → ABSTAIN
    _unit(session, "thong_tu", "tt_1", date_effective=D(2021, 1, 1))
    _unit(session, "thong_tu", "tt_2", date_effective=D(2021, 1, 1))
    r = repo.resolve_conflict(session, ["tt_1", "tt_2"], AS_OF)
    assert r.unresolved and r.rule == "abstain:tie"
