"""L14 Human Knowledge-Ops — hàng đợi HITL + flywheel 'output duyệt → gold set'.

Chất lượng pháp lý đến từ vòng chuyên gia↔dữ liệu, không từ model. Tool: duyệt
norm_relation (needs_review) → approved mở cổng materialize (W2); xuất case đã-duyệt
thành gold (eval moat). Đây là layer người+tool, không phải bước duyệt lẻ.
"""

from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..w2.models import NormRelation
from .eval_harness import GoldCase


def pending_relations(session: Session, *, limit: int = 100) -> list[NormRelation]:
    """Review and application backlog; approval alone must not hide unapplied changes."""
    return list(session.scalars(
        sa.select(NormRelation).where(sa.or_(
            NormRelation.review_status == "needs_review",
            sa.and_(NormRelation.review_status == "approved",
                    NormRelation.relation_type.in_(["amends", "repeals", "replaces"]),
                    NormRelation.materialized_at.is_(None)),
        ))
        .order_by(NormRelation.relation_type).limit(limit)))


def _set_review(session: Session, rel_id: int, status: str) -> NormRelation:
    rel = session.get(NormRelation, rel_id, with_for_update=True)
    if rel is None:
        raise LookupError(f"norm_relation {rel_id} không tồn tại")
    if rel.materialized_at is not None and status != "approved":
        raise ValueError("cannot reject an applied relation; publish a reviewed correction")
    rel.review_status = status
    session.flush()
    return rel


def approve_relation(session: Session, rel_id: int) -> NormRelation:
    """Duyệt → mở cổng materialize (W2 áp vào kho bitemporal)."""
    return _set_review(session, rel_id, "approved")


def reject_relation(session: Session, rel_id: int) -> NormRelation:
    return _set_review(session, rel_id, "rejected")


def apply_reviewed_amendment(session, rel_id: int, replacement_text: str, lang="vi"):
    """Operator-provided full replacement of one resolved unit; atomic and replay-safe."""
    import hashlib

    from ..w2 import repo
    from ..w2.models import Unit
    rel = session.get(NormRelation, rel_id, with_for_update=True)
    if rel is None:
        raise LookupError("relation not found")
    if (rel.relation_type != "amends" or rel.dst_unit_id is None
            or rel.effective_date is None or rel.review_status == "rejected"):
        raise ValueError("amendment requires a resolved unit/date and a non-rejected relation")
    if lang not in {"vi", "en"} or not replacement_text.strip():
        raise ValueError("replacement text and supported language are required")
    unit = session.get(Unit, rel.dst_unit_id)
    if unit is None or unit.document_id != rel.dst_doc_id:
        raise ValueError("amendment target does not belong to the target document")
    digest = hashlib.sha256((lang + "\n" + replacement_text).encode()).hexdigest()
    if rel.materialized_at is not None:
        if rel.applied_payload_hash != digest:
            raise ValueError("applied amendment payload is immutable")
        return rel
    repo.apply_amendment(session, unit.eid, replacement_text, rel.effective_date,
                         source_relation_id=f"rel:{rel.id}", lang=lang, order_key=rel.order_key)
    rel.review_status = "approved"
    rel.applied_payload_hash = digest
    rel.materialized_at = repo._db_now(session)
    session.flush()
    return rel


def append_gold(path: str | Path, case: GoldCase) -> None:
    """Flywheel — ghi 1 case ĐÃ DUYỆT vào gold set (JSONL). Chuyên gia ký → gold."""
    rec = {
        "case_id": case.case_id, "query": case.query, "as_of": case.as_of.isoformat(),
        "gold_eids": case.gold_eids, "required_eids": case.required_eids,
        "expect_abstain": case.expect_abstain, "tags": case.tags,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
