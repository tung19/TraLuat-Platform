"""Repository bitemporal trên Postgres — cùng ngữ nghĩa engine thuần (slice-1),
nhưng bất biến no-overlap do DB (GiST EXCLUDE) gác, không do app.

apply_amendment chạy trong 1 transaction: đóng bản mở + chèn bản mới. Nếu tạo
chồng khoảng → Postgres RAISE (uv_no_overlap) — fail-loud ở tầng dữ liệu.
"""

from __future__ import annotations

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .bitemporal import BitemporalCorruption
from .models import Unit, UnitVersion


def _unit_id(s: Session, eid: str) -> int:
    uid = s.scalar(sa.select(Unit.id).where(Unit.eid == eid))
    if uid is None:
        raise LookupError(f"unit eid không tồn tại: {eid}")
    return uid


def reconstruct_as_of(
    s: Session, eid: str, as_of: dt.date, lang: str = "vi",
    known_as_of: dt.datetime | None = None,
) -> str | None:
    """Văn bản tại ngày T (SQL). None nếu vắng/bãi bỏ; raise nếu >1 dòng (hỏng)."""
    known = known_as_of or dt.datetime.now(dt.timezone.utc)
    rows = s.execute(
        sa.select(UnitVersion.text)
        .join(Unit, Unit.id == UnitVersion.unit_id)
        .where(
            Unit.eid == eid,
            UnitVersion.lang == lang,
            UnitVersion.valid_from <= as_of,
            sa.or_(UnitVersion.valid_to.is_(None), as_of < UnitVersion.valid_to),
            UnitVersion.tx_from <= known,
            sa.or_(UnitVersion.tx_to.is_(None), known < UnitVersion.tx_to),
        )
    ).all()
    if len(rows) > 1:
        raise BitemporalCorruption(f"{eid}@{as_of}: {len(rows)} dòng in-force")
    return rows[0][0] if rows else None


def apply_amendment(
    s: Session, eid: str, new_text: str | None, effective_date: dt.date, *,
    source_relation_id: str | None = None, order_key: int = 0,
    applies_from: dt.date | None = None, lang: str = "vi",
    status: str = "con_hieu_luc", transitional: bool = False,
) -> None:
    """Đóng bản mở tại effective_date + chèn bản mới. Idempotent theo relation id.

    GiST EXCLUDE gác overlap; same-date fold theo order_key.
    """
    uid = _unit_id(s, eid)

    # idempotent
    if source_relation_id:
        exists = s.scalar(
            sa.select(sa.func.count())
            .select_from(UnitVersion)
            .where(
                UnitVersion.source_relation_id == source_relation_id,
                UnitVersion.valid_from == effective_date,
                UnitVersion.tx_to.is_(None),
            )
        )
        if exists:
            return

    open_rows = list(
        s.scalars(
            sa.select(UnitVersion).where(
                UnitVersion.unit_id == uid,
                UnitVersion.lang == lang,
                UnitVersion.tx_to.is_(None),
                UnitVersion.valid_to.is_(None),
            ).with_for_update()  # serialize per-unit (chaos C2)
        )
    )

    # same-date fold
    for v in open_rows:
        if v.valid_from == effective_date:
            if order_key >= v.order_key:
                v.text, v.status, v.order_key = new_text, status, order_key
                v.source_relation_id = source_relation_id
                v.applies_from, v.transitional = applies_from, transitional
            s.flush()
            return

    # đóng bản phủ trước effective_date
    for v in open_rows:
        if v.valid_from < effective_date:
            v.valid_to = effective_date
    s.flush()  # commit việc đóng trước khi chèn (tránh EXCLUDE tự-đụng trong 1 flush)

    s.add(
        UnitVersion(
            unit_id=uid, lang=lang, valid_from=effective_date, valid_to=None,
            applies_from=applies_from, text=new_text, status=status,
            transitional=transitional, source_relation_id=source_relation_id,
            order_key=order_key,
        )
    )
    s.flush()  # EXCLUDE kiểm tại đây → raise nếu overlap


def repeal(s: Session, eid: str, effective_date: dt.date, **kw) -> None:
    kw.setdefault("status", "het_hieu_luc")
    apply_amendment(s, eid, None, effective_date, **kw)
