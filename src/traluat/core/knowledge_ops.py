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

from .eval_harness import GoldCase
from ..w2.models import NormRelation


def pending_relations(session: Session, *, limit: int = 100) -> list[NormRelation]:
    """Hàng đợi HITL — quan hệ chờ duyệt (ưu tiên operative: repeals/replaces/amends)."""
    return list(session.scalars(
        sa.select(NormRelation).where(NormRelation.review_status == "needs_review")
        .order_by(NormRelation.relation_type).limit(limit)))


def _set_review(session: Session, rel_id: int, status: str) -> NormRelation:
    rel = session.get(NormRelation, rel_id)
    if rel is None:
        raise LookupError(f"norm_relation {rel_id} không tồn tại")
    rel.review_status = status
    session.flush()
    return rel


def approve_relation(session: Session, rel_id: int) -> NormRelation:
    """Duyệt → mở cổng materialize (W2 áp vào kho bitemporal)."""
    return _set_review(session, rel_id, "approved")


def reject_relation(session: Session, rel_id: int) -> NormRelation:
    return _set_review(session, rel_id, "rejected")


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
