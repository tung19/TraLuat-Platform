"""End-to-end (Postgres): đồ thị tri thức — neighborhood (viz) + Researcher multihop."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2 import repo
from traluat.w2.db import make_engine
from traluat.w2.models import NormRelation, Unit
from traluat.w3 import EchoLLMGateway
from traluat.w4 import CaseInput, ReasoningEngine

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


def _uid(s, eid):
    return s.scalar(sa.select(Unit.id).where(Unit.eid == eid))


def _edge(s, src, dst, rtype):
    doc = s.scalar(sa.select(Unit.document_id).where(Unit.eid == src))
    s.add(NormRelation(relation_type=rtype, src_doc_id=doc, dst_doc_id=doc,
                       src_unit_id=_uid(s, src), dst_unit_id=_uid(s, dst),
                       review_status="approved"))
    s.flush()


def test_neighborhood_subgraph(session: Session):
    _edge(session, "nd99__dieu_1", "nd99__dieu_5", "guides")
    _edge(session, "nd99__dieu_3", "nd99__dieu_5", "cites")
    nb = repo.neighborhood(session, "nd99__dieu_5")
    assert nb["center"] == "nd99__dieu_5"
    eids = {n["eid"] for n in nb["nodes"]}
    assert {"nd99__dieu_1", "nd99__dieu_3", "nd99__dieu_5"} <= eids
    assert {e["type"] for e in nb["edges"]} == {"guides", "cites"}


def test_graphstore_port_matches_repo(session: Session):
    # ADR-0001: PostgresGraphStore port cho CÙNG kết quả như repo (seam để đổi engine)
    from traluat.w2 import PostgresGraphStore
    _edge(session, "nd99__dieu_1", "nd99__dieu_5", "guides")
    gs = PostgresGraphStore(session)
    assert gs.multihop("nd99__dieu_1", ["guides"], as_of=D(2022, 1, 1)) == \
           repo.multihop(session, "nd99__dieu_1", ["guides"], as_of=D(2022, 1, 1))
    assert gs.neighborhood("nd99__dieu_5")["center"] == "nd99__dieu_5"


def test_researcher_pulls_graph_linked_article(session: Session):
    # guides: Điều 1 → Điều 5. Query trúng Điều 1 (không trúng Điều 5) → multihop kéo Điều 5.
    _edge(session, "nd99__dieu_1", "nd99__dieu_5", "guides")
    eng = ReasoningEngine(session, gateway=EchoLLMGateway())      # graph_hops=1 (mặc định)
    adj = eng.analyze(CaseInput(facts="phạm vi điều chỉnh của nghị định"), as_of=D(2022, 1, 1))
    veids = {a.unit_eid for a in adj.verified_articles}
    assert "nd99__dieu_1" in veids       # retrieve trực tiếp
    assert "nd99__dieu_5" in veids       # KÉO qua đồ thị (guides), dù query không trúng

    # tắt graph_hops → không kéo
    eng0 = ReasoningEngine(session, gateway=EchoLLMGateway(), graph_hops=0)
    adj0 = eng0.analyze(CaseInput(facts="phạm vi điều chỉnh của nghị định"), as_of=D(2022, 1, 1))
    assert "nd99__dieu_5" not in {a.unit_eid for a in adj0.verified_articles}
