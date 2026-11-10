"""Neo4jGraphStore (ADR-0001 option c) — PROJECTION read-only của norm_relation.

★ Cột-mốc consistency (giải F1/F2): Postgres là SoR. Neo4j chỉ giữ CẤU TRÚC đồ thị
(điều nào trỏ điều nào), rebuild từ `project_to_neo4j`. NGUYÊN VĂN + effect_status
LUÔN lấy từ Postgres (pin snapshot) — Neo4j KHÔNG trả text. Edge mang effective_date
→ Cypher lọc `<= as_of` (bitemporal-aware). Projection phản ánh norm_relation TẠI
LẦN SYNC cuối (gọi sau materialize); cạnh luật đổi hiếm + có effective_date nên cửa
sổ trễ không ảnh hưởng 'văn bản tại ngày T' (text vẫn từ Postgres).

Import lười (driver neo4j optional). Cắm vào ReasoningEngine qua GraphStore port.
"""

from __future__ import annotations

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Session, aliased

from .models import NormRelation, Unit


def project_to_neo4j(session: Session, driver, *, database: str = "neo4j") -> int:
    """Rebuild đồ thị trong Neo4j từ norm_relation (unit-level). Idempotent (xoá+dựng)."""
    units = session.execute(sa.select(Unit.eid, Unit.label, Unit.unit_type)).all()
    Src, Dst = aliased(Unit), aliased(Unit)
    rels = session.execute(
        sa.select(Src.eid, Dst.eid, NormRelation.relation_type,
                  NormRelation.effective_date, NormRelation.review_status)
        .join(Src, Src.id == NormRelation.src_unit_id)
        .join(Dst, Dst.id == NormRelation.dst_unit_id)).all()

    with driver.session(database=database) as s:
        s.run("MATCH (n:Unit) DETACH DELETE n")                 # full rebuild (đồ thị nhỏ)
        s.run("UNWIND $rows AS r MERGE (u:Unit {eid:r.eid}) SET u.label=r.label, u.utype=r.utype",
              rows=[{"eid": e, "label": l, "utype": t} for e, l, t in units])
        s.run(
            "UNWIND $rows AS r MATCH (a:Unit {eid:r.s}),(b:Unit {eid:r.d}) "
            "MERGE (a)-[e:REL {type:r.t}]->(b) SET e.effective_date=r.ed, e.review_status=r.rs",
            rows=[{"s": se, "d": de, "t": rt,
                   "ed": ed.isoformat() if ed else None, "rs": rs}
                  for se, de, rt, ed, rs in rels])
    return len(rels)


def sync_relation(driver, session: Session, rel: NormRelation, *, database: str = "neo4j") -> bool:
    """Incremental — upsert MỘT cạnh vào Neo4j (gọi từ post-materialize hook). Rẻ hơn
    full rebuild. Chỉ cạnh cấp UNIT (có src_unit/dst_unit). Trả True nếu đã sync."""
    if rel.src_unit_id is None or rel.dst_unit_id is None:
        return False
    rows = dict(session.execute(
        sa.select(Unit.id, Unit.eid).where(
            Unit.id.in_([rel.src_unit_id, rel.dst_unit_id]))).all())
    se, de = rows.get(rel.src_unit_id), rows.get(rel.dst_unit_id)
    if not (se and de):
        return False
    labels = dict(session.execute(
        sa.select(Unit.eid, Unit.label).where(Unit.eid.in_([se, de]))).all())
    with driver.session(database=database) as s:
        s.run("MERGE (:Unit {eid:$e}) ", e=se)
        s.run("MATCH (u:Unit {eid:$e}) SET u.label=$l", e=se, l=labels.get(se))
        s.run("MERGE (:Unit {eid:$e}) ", e=de)
        s.run("MATCH (u:Unit {eid:$e}) SET u.label=$l", e=de, l=labels.get(de))
        s.run("MATCH (a:Unit {eid:$s}),(b:Unit {eid:$d}) MERGE (a)-[e:REL {type:$t}]->(b) "
              "SET e.effective_date=$ed, e.review_status=$rs",
              s=se, d=de, t=rel.relation_type,
              ed=rel.effective_date.isoformat() if rel.effective_date else None,
              rs=rel.review_status)
    return True


def enable_neo4j_sync(driver, *, database: str = "neo4j") -> None:
    """Đăng ký hook: mỗi materialize thành công → sync cạnh sang Neo4j (option a)."""
    from . import repo
    repo.register_post_materialize(lambda s, rel: sync_relation(driver, s, rel, database=database))


class Neo4jGraphStore:
    def __init__(self, driver, database: str = "neo4j") -> None:
        self.driver = driver
        self.database = database

    def multihop(self, start_eid, rel_types, max_hops=3, as_of=None):
        as_of = (as_of or dt.date.max).isoformat()
        cy = (
            "MATCH p=(s:Unit {eid:$start})-[rels:REL*1..%d]->(t:Unit) "
            "WHERE all(r IN rels WHERE r.type IN $types AND "
            "          (r.effective_date IS NULL OR r.effective_date <= $as_of)) "
            "RETURN DISTINCT t.eid AS eid" % max_hops)
        with self.driver.session(database=self.database) as s:
            return sorted(r["eid"] for r in s.run(cy, start=start_eid,
                                                  types=list(rel_types), as_of=as_of)
                          if r["eid"] != start_eid)

    def neighborhood(self, eid, as_of=None, rel_types=None, max_hops=1):
        # 1-hop thuần Cypher (không phụ thuộc APOC) — đủ cho viz FR-37 cơ bản.
        cy = (
            "MATCH (c:Unit {eid:$e}) "
            "OPTIONAL MATCH (c)-[r:REL]-(n:Unit) "
            "WHERE $types IS NULL OR r.type IN $types "
            "RETURN c.eid AS c_eid, c.label AS c_label, c.utype AS c_utype, "
            "collect(DISTINCT {eid:n.eid, label:n.label, type:n.utype}) AS nbrs, "
            "collect(DISTINCT {src:startNode(r).eid, dst:endNode(r).eid, "
            "                  type:r.type, review_status:r.review_status}) AS edges")
        with self.driver.session(database=self.database) as s:
            rec = s.run(cy, e=eid, types=list(rel_types) if rel_types else None).single()
        if rec is None:
            return {"center": eid, "nodes": [], "edges": []}
        nodes = [{"eid": rec["c_eid"], "label": rec["c_label"], "type": rec["c_utype"]}]
        nodes += [n for n in rec["nbrs"] if n.get("eid")]
        edges = [e for e in rec["edges"] if e.get("src")]
        return {"center": eid, "nodes": nodes, "edges": edges}
