"""Neo4j projection (ADR-0001 c) — Cypher multihop ≡ CTE (parallel-path §8-A).
@graph. Skip nếu chưa cài driver neo4j hoặc Neo4j không chạy (profile graph)."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

pytest.importorskip("neo4j")
from neo4j import GraphDatabase  # noqa: E402

from traluat.w1 import build_ingest, load_to_w2  # noqa: E402
from traluat.w2 import PostgresGraphStore  # noqa: E402
from traluat.w2.db import make_engine  # noqa: E402
from traluat.w2.graph_neo4j import (  # noqa: E402
    Neo4jGraphStore, gds_communities, gds_pagerank, project_to_neo4j)


def _has_gds(driver) -> bool:
    try:
        with driver.session() as s:
            s.run("RETURN gds.version()").single()
        return True
    except Exception:  # noqa: BLE001
        return False
from traluat.w2.models import NormRelation, Unit  # noqa: E402

D = dt.date
FRBR = "trl:vn/nd/99/2020"
from tests.test_w1_structure import SAMPLE  # noqa: E402

_BOLT = "bolt://localhost:7687"
_AUTH = ("neo4j", "traluat-neo4j-pw")


@pytest.fixture(scope="module")
def driver():
    try:
        d = GraphDatabase.driver(_BOLT, auth=_AUTH)
        d.verify_connectivity()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Neo4j không chạy (docker compose --profile graph up): {e}")
    yield d
    d.close()


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


def _edge(s, src, dst, rtype, eff=None):
    doc = s.scalar(sa.select(Unit.document_id).where(Unit.eid == src))
    s.add(NormRelation(
        relation_type=rtype, src_doc_id=doc, dst_doc_id=doc, effective_date=eff,
        src_unit_id=s.scalar(sa.select(Unit.id).where(Unit.eid == src)),
        dst_unit_id=s.scalar(sa.select(Unit.id).where(Unit.eid == dst)),
        review_status="approved"))
    s.flush()


def test_neo4j_multihop_matches_cte(session: Session, driver):
    _edge(session, "nd99__dieu_1", "nd99__dieu_5", "guides")
    _edge(session, "nd99__dieu_3", "nd99__dieu_5", "cites")
    _edge(session, "nd99__dieu_5", "nd99__dieu_1", "cites", eff=D(2025, 1, 1))  # chưa hiệu lực@2022
    project_to_neo4j(session, driver)

    pg, ne = PostgresGraphStore(session), Neo4jGraphStore(driver)
    for start, types in [("nd99__dieu_1", ["guides", "cites"]),
                         ("nd99__dieu_3", ["cites"]),
                         ("nd99__dieu_1", ["cites"])]:
        assert ne.multihop(start, types, max_hops=3, as_of=D(2022, 1, 1)) == \
               pg.multihop(start, types, max_hops=3, as_of=D(2022, 1, 1)), (start, types)

    # edge 2025 → tại 2025 cạnh dieu_5→dieu_1 bật (bitemporal-aware, cả 2 engine)
    assert ne.multihop("nd99__dieu_5", ["cites"], as_of=D(2025, 6, 1)) == \
           pg.multihop("nd99__dieu_5", ["cites"], as_of=D(2025, 6, 1))


def test_auto_sync_on_materialize(session: Session, driver):
    # option (a): materialize cạnh approved → hook tự sync sang Neo4j (không full-project)
    from traluat.w2 import repo
    from traluat.w2.graph_neo4j import enable_neo4j_sync
    from traluat.w2.models import NormRelation

    with driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")          # dọn Neo4j để cô lập
    repo.clear_post_materialize_hooks()
    enable_neo4j_sync(driver)
    try:
        _edge(session, "nd99__dieu_1", "nd99__dieu_5", "guides")   # review_status=approved
        rel = session.scalars(sa.select(NormRelation)).first()
        assert repo.materialize(session, rel) is True              # hook → sync cạnh
        assert Neo4jGraphStore(driver).multihop(
            "nd99__dieu_1", ["guides"], as_of=D(2022, 1, 1)) == ["nd99__dieu_5"]
    finally:
        repo.clear_post_materialize_hooks()         # KHÔNG rò hook sang test khác


def test_neo4j_neighborhood(session: Session, driver):
    _edge(session, "nd99__dieu_1", "nd99__dieu_5", "guides")
    project_to_neo4j(session, driver)
    nb = Neo4jGraphStore(driver).neighborhood("nd99__dieu_5")
    assert nb["center"] == "nd99__dieu_5"
    assert {e["type"] for e in nb["edges"]} == {"guides"}


def test_gds_pagerank_and_community(session: Session, driver):
    if not _has_gds(driver):
        pytest.skip("Neo4j không có GDS plugin")
    # Điều 5 bị viện dẫn NHIỀU NHẤT → PageRank cao nhất ('luật trọng tâm')
    _edge(session, "nd99__dieu_1", "nd99__dieu_5", "cites")
    _edge(session, "nd99__dieu_3", "nd99__dieu_5", "cites")
    _edge(session, "nd99__dieu_1", "nd99__dieu_3", "cites")
    project_to_neo4j(session, driver)

    pr = gds_pagerank(driver)
    assert pr[0][0] == "nd99__dieu_5"               # trọng tâm = bị dẫn chiếu nhiều nhất

    comm = gds_communities(driver)
    # 3 điều liên kết → cùng 1 community
    assert comm["nd99__dieu_1"] == comm["nd99__dieu_5"] == comm["nd99__dieu_3"]
