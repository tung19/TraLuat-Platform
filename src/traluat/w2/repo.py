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
from .models import NormRelation, Unit, UnitVersion

# Quan hệ auto-safe (không chi phối hiệu lforce): repeals/replaces/amends KHÔNG ở đây.
AUTO_SAFE_TYPES = {"cites", "guides", "hierarchy", "conflicts"}


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

    # bản current-belief phủ effective_date (mở hoặc đóng) — SELECT FOR UPDATE (chaos C2)
    covering = list(
        s.scalars(
            sa.select(UnitVersion).where(
                UnitVersion.unit_id == uid,
                UnitVersion.lang == lang,
                UnitVersion.tx_to.is_(None),
                UnitVersion.valid_from <= effective_date,
                sa.or_(UnitVersion.valid_to.is_(None), effective_date < UnitVersion.valid_to),
            ).with_for_update()
        )
    )
    if len(covering) > 1:
        raise BitemporalCorruption(f"{eid}@{effective_date}: {len(covering)} bản phủ")

    if covering:
        v = covering[0]
        if v.valid_from == effective_date:  # same-date fold
            if order_key >= v.order_key:
                v.text, v.status, v.order_key = new_text, status, order_key
                v.source_relation_id = source_relation_id
                v.applies_from, v.transitional = applies_from, transitional
            s.flush()
            return
        new_to = v.valid_to            # ★ interval-split: tail mở hoặc giữa chuỗi
        v.valid_to = effective_date
        s.flush()                      # đóng trước, tránh EXCLUDE tự-đụng trong 1 flush
    else:
        new_to = None

    s.add(
        UnitVersion(
            unit_id=uid, lang=lang, valid_from=effective_date, valid_to=new_to,
            applies_from=applies_from, text=new_text, status=status,
            transitional=transitional, source_relation_id=source_relation_id,
            order_key=order_key,
        )
    )
    s.flush()  # EXCLUDE kiểm tại đây → raise nếu overlap


def repeal(s: Session, eid: str, effective_date: dt.date, **kw) -> None:
    kw.setdefault("status", "het_hieu_luc")
    apply_amendment(s, eid, None, effective_date, **kw)


# ── Materialize gate (W1 C1 / principle #8): W2 KHÔNG tin W1 vô điều kiện ─────────
class NotApproved(Exception):
    """Quan hệ chưa đủ điều kiện materialize (chưa duyệt / confidence thấp)."""


def _eid(s: Session, unit_id: int) -> str:
    return s.scalar(sa.select(Unit.eid).where(Unit.id == unit_id))


def materialize(s: Session, rel: NormRelation, *, theta: float = 0.9) -> bool:
    """Áp một norm_relation vào kho bitemporal — CHỈ khi qua cổng.

    Cổng (C1): materialize khi `review_status='approved'`, HOẶC confidence≥θ cho
    loại AUTO-SAFE. repeals/replaces/amends **KHÔNG BAO GIỜ auto** (phải approved).
    Trả True nếu đã materialize, False nếu bị chặn (chờ duyệt).
    """
    approved = rel.review_status == "approved"
    auto_ok = rel.relation_type in AUTO_SAFE_TYPES and (rel.confidence or 0.0) >= theta
    if not (approved or auto_ok):
        return False  # chặn — chờ hàng đợi duyệt (không corrupt kho)

    if rel.relation_type in {"repeals", "replaces"}:
        _materialize_repeal(s, rel)
        return True
    # amends cần TEXT mới (W1 resolve từ văn bản sửa đổi) — ngoài phạm vi slice-3.
    # cites/guides/hierarchy/conflicts: quan hệ đồ thị, không chạm unit_version.
    return True


def _materialize_repeal(s: Session, rel: NormRelation) -> None:
    eff = rel.effective_date
    if eff is None:
        raise BitemporalCorruption(f"relation {rel.id}: repeals thiếu effective_date")
    if rel.dst_unit_id is not None:
        repeal(s, _eid(s, rel.dst_unit_id), eff, source_relation_id=f"rel:{rel.id}")
    else:
        # ★ G3-fix: repeal CẢ VĂN BẢN → tombstone mọi unit của dst_doc
        eids = s.scalars(sa.select(Unit.eid).where(Unit.document_id == rel.dst_doc_id)).all()
        for e in eids:
            repeal(s, e, eff, source_relation_id=f"rel:{rel.id}:{e}")
