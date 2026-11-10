"""Precedent store — nạp án lệ + match theo điều tựa vào (nuôi prune_unsupported).

match_by_eids: án lệ nào tựa vào ÍT NHẤT MỘT eid trong tập ứng viên → candidate.
Auditor.prune_unsupported sau đó bỏ án lệ mà mọi điều tựa vào đều bị loại.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..w2.models import PrecedentRow
from .types import Precedent


def add_precedent(
    session: Session, precedent_id: str, cited_eids: list[str], *,
    situation: str = "", solution: str = "",
) -> None:
    """Upsert án lệ theo precedent_id (idempotent)."""
    stmt = pg_insert(PrecedentRow).values(
        precedent_id=precedent_id, cited_eids=cited_eids,
        situation=situation, solution=solution)
    stmt = stmt.on_conflict_do_update(
        index_elements=["precedent_id"],
        set_={"cited_eids": cited_eids, "situation": situation, "solution": solution})
    session.execute(stmt)
    session.flush()


def match_by_eids(session: Session, eids: list[str]) -> list[Precedent]:
    """Án lệ tựa vào ≥1 eid trong `eids` (JSONB ?| — push-down SQL)."""
    if not eids:
        return []
    rows = session.scalars(
        sa.select(PrecedentRow).where(
            PrecedentRow.cited_eids.op("?|")(array(eids)))).all()
    return [Precedent(precedent_id=r.precedent_id, cited_unit_eids=list(r.cited_eids),
                      situation=r.situation or "", solution=r.solution or "")
            for r in rows]
