"""Repository bitemporal trên Postgres — cùng ngữ nghĩa engine thuần (slice-1),
nhưng bất biến no-overlap do DB (GiST EXCLUDE) gác, không do app.

apply_amendment chạy trong 1 transaction: đóng bản mở + chèn bản mới. Nếu tạo
chồng khoảng → Postgres RAISE (uv_no_overlap) — fail-loud ở tầng dữ liệu.
"""

from __future__ import annotations

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Session

from collections import defaultdict
from dataclasses import dataclass, field

from .. import legal_rule_base as lrb
from .bitemporal import BitemporalCorruption, EffectStatus
from .models import Document, NormRelation, Unit, UnitVersion

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


# Đơn vị KẾT CẤU (có tiêu đề, thường không có text riêng) vs đơn vị NỘI DUNG.
_STRUCTURAL = {"phan", "chuong", "muc", "tieu_muc"}


def document_as_of(
    s: Session, frbr_uri: str, as_of: dt.date, lang: str = "vi",
    known_as_of: dt.datetime | None = None,
) -> str:
    """Ghép CẢ VĂN BẢN tại ngày T — M4-fix: duyệt CÂY (parent_id) theo ordinal,
    KHÔNG ghép phẳng. Đơn vị bị bãi bỏ (tombstone) → bỏ; đơn vị kết cấu (Chương…)
    không có version → in tiêu đề; đơn vị nội dung in-force → in label + text.
    """
    doc = s.scalar(sa.select(Document).where(Document.frbr_uri == frbr_uri))
    if doc is None:
        raise LookupError(f"document không tồn tại: {frbr_uri}")
    units = list(s.scalars(sa.select(Unit).where(Unit.document_id == doc.id)))
    has_version = set(
        s.scalars(
            sa.select(UnitVersion.unit_id).where(
                UnitVersion.unit_id.in_([u.id for u in units])
            ).distinct()
        )
    )
    children: dict[int | None, list[Unit]] = defaultdict(list)
    for u in units:
        children[u.parent_id].append(u)
    for kids in children.values():
        kids.sort(key=lambda u: u.ordinal)

    lines: list[str] = []

    def walk(parent_id: int | None, depth: int) -> None:
        for u in children.get(parent_id, []):
            if u.id in has_version:
                txt = reconstruct_as_of(s, u.eid, as_of, lang, known_as_of)
                if txt is not None:                       # in-force → in nội dung
                    lines.append(f"{'  ' * depth}{u.label}. {txt}")
                # tombstone/not-yet → bỏ dòng của chính nó (vẫn duyệt con)
            elif u.unit_type in _STRUCTURAL:              # kết cấu → in tiêu đề
                lines.append(f"{'  ' * depth}{u.label}")
            walk(u.id, depth + 1)

    walk(None, 0)
    return "\n".join(lines)


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


# ── effect_status qua DB (B3-fix: enum, không bool) ─────────────────────────────
def effect_status(
    s: Session, eid: str, as_of: dt.date, lang: str = "vi",
    known_as_of: dt.datetime | None = None,
) -> EffectStatus:
    known = known_as_of or dt.datetime.now(dt.timezone.utc)
    rows = list(
        s.execute(
            sa.select(UnitVersion.valid_from, UnitVersion.valid_to,
                      UnitVersion.text, UnitVersion.transitional)
            .join(Unit, Unit.id == UnitVersion.unit_id)
            .where(
                Unit.eid == eid, UnitVersion.lang == lang,
                UnitVersion.tx_from <= known,
                sa.or_(UnitVersion.tx_to.is_(None), known < UnitVersion.tx_to),
            )
        )
    )
    if not rows:
        return EffectStatus.ABSENT
    covering = [r for r in rows if r.valid_from <= as_of and (r.valid_to is None or as_of < r.valid_to)]
    if len(covering) > 1:
        raise BitemporalCorruption(f"{eid}@{as_of}: {len(covering)} dòng in-force")
    if covering:
        return EffectStatus.EXPIRED_CITABLE if covering[0].text is None else EffectStatus.IN_FORCE
    if as_of < min(r.valid_from for r in rows):
        return EffectStatus.NOT_YET
    if any(r.transitional for r in rows):
        return EffectStatus.TRANSITIONAL_APPLIES
    return EffectStatus.EXPIRED_CITABLE


# ── R5: correct_valid_from (tx-time — giữ 'điều hệ thống từng tin') ───────────────
def correct_valid_from(
    s: Session, version_id: int, correct_valid_from: dt.date,
    now: dt.datetime | None = None,
) -> None:
    """Sửa ngày hiệu lực bị NHẬP SAI — KHÔNG ghi đè (chaos: in-place UPDATE phá tx-time).

    Đóng bản sai ở trục transaction-time (tx_to=now, giữ để audit) + chèn bản ĐÚNG
    (tx_from=now). → truy vấn với known_as_of trong quá khứ vẫn trả điều hệ-thống-từng-tin.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    v = s.get(UnitVersion, version_id)
    if v is None or v.tx_to is not None:
        raise BitemporalCorruption(f"version {version_id} không tồn tại / không còn current")
    v.tx_to = now  # đóng tin cũ (vẫn giữ dòng)
    s.flush()
    s.add(
        UnitVersion(
            unit_id=v.unit_id, lang=v.lang, valid_from=correct_valid_from, valid_to=v.valid_to,
            applies_from=v.applies_from, text=v.text, tx_from=now, tx_to=None,
            status=v.status, transitional=v.transitional,
            source_relation_id=v.source_relation_id, order_key=v.order_key,
        )
    )
    s.flush()


# ── §4: resolve_conflict (deterministic; cổng-hiệu-lforce-TRƯỚC → lex rules → abstain) ──
@dataclass
class ConflictResult:
    winner_eid: str | None
    losers: list[tuple[str, str]] = field(default_factory=list)  # (eid, lý do/status)
    rule: str = ""              # lex_superior | lex_posterior | abstain:<reason>
    explanation: str = ""
    unresolved: bool = False    # True → đẩy HUMAN (principle #6), không auto


def resolve_conflict(
    s: Session, eids: list[str], as_of: dt.date, question_type: str = "general",
) -> ConflictResult:
    """Giải tập điều ĐÃ-được-flag là chọi nhau. KHÔNG tự phát hiện (đó là FR-41).

    ① Cổng hiệu lực (effect_status@as_of): hết hiệu lực → cite nhưng KHÔNG tranh thắng.
    ② lex superior (authority_rank@as_of, rule base) → ③ lex posterior (cùng rank, mới hơn)
    → ④ hoà / rank mơ hồ / không-in-force → ABSTAIN→human.
    """
    items = []
    for eid in eids:
        row = s.execute(
            sa.select(Document.doc_type, Document.date_effective)
            .join(Unit, Unit.document_id == Document.id).where(Unit.eid == eid)
        ).first()
        if row is None:
            raise LookupError(f"unit eid không tồn tại: {eid}")
        st = effect_status(s, eid, as_of)
        items.append({
            "eid": eid, "doc_type": row.doc_type, "date_effective": row.date_effective,
            "status": st, "rank": lrb.rank_of(row.doc_type, as_of),
        })

    # ① cổng hiệu lực
    eligible = [it for it in items if it["status"] in (EffectStatus.IN_FORCE, EffectStatus.TRANSITIONAL_APPLIES)]
    all_losers = [(it["eid"], it["status"].value) for it in items]

    if not eligible:
        return ConflictResult(None, all_losers, "abstain:no_in_force",
                              "Không bên nào còn hiệu lực @as_of → human.", unresolved=True)
    if any(it["rank"] is None for it in eligible):
        return ConflictResult(None, all_losers, "abstain:rank_undetermined",
                              "doc_type mơ hồ (thiếu cơ quan) → human.", unresolved=True)

    def losers_except(win_eid):
        return [(it["eid"], it["status"].value) for it in items if it["eid"] != win_eid]

    # ② lex superior
    max_rank = max(it["rank"] for it in eligible)
    top = [it for it in eligible if it["rank"] == max_rank]
    if len(top) == 1:
        w = top[0]
        return ConflictResult(w["eid"], losers_except(w["eid"]), "lex_superior",
                              f"Hiệu lforce cao nhất (rank {max_rank}) thắng.")

    # ③ lex posterior (cùng rank — scaffold xấp xỉ 'cùng cơ quan'; mới hơn thắng)
    dates = [it["date_effective"] for it in top]
    if all(d is not None for d in dates) and len(set(dates)) == len(dates):
        w = max(top, key=lambda it: it["date_effective"])
        return ConflictResult(w["eid"], losers_except(w["eid"]), "lex_posterior",
                              "Cùng rank → ban hành/hiệu lực sau thắng.")

    # ④ hoà / posterior⟂specialis → ABSTAIN (principle #6)
    return ConflictResult(None, all_losers, "abstain:tie",
                          "Cùng rank không phân định (posterior⟂specialis/cùng ngày) → human.",
                          unresolved=True)


# ── §5.1: multihop norm-graph (FK + recursive CTE; bounded + cycle-safe + as_of) ──
def multihop(
    s: Session, start_eid: str, rel_types: list[str], max_hops: int = 3,
    as_of: dt.date | None = None,
) -> list[str]:
    """Các đơn vị tới được từ start_eid qua rel_types (dẫn chiếu/hướng dẫn…).

    Bounded-hop (performance §4 guard) + chống chu trình (path array) + lọc hiệu lực
    quan hệ theo as_of. AGE để sau — FK+CTE trước (stack-db: hoãn AGE).
    """
    start_id = _unit_id(s, start_eid)
    as_of = as_of or dt.date.max
    sql = sa.text("""
        WITH RECURSIVE reach(unit_id, depth, path) AS (
            SELECT CAST(:start_id AS integer), 0, ARRAY[CAST(:start_id AS integer)]
          UNION ALL
            SELECT nr.dst_unit_id, r.depth + 1, r.path || nr.dst_unit_id
            FROM reach r
            JOIN norm_relation nr ON nr.src_unit_id = r.unit_id
            WHERE nr.relation_type = ANY(CAST(:types AS text[]))
              AND nr.dst_unit_id IS NOT NULL
              AND (nr.effective_date IS NULL OR nr.effective_date <= :as_of)
              AND r.depth < :max_hops
              AND NOT (nr.dst_unit_id = ANY(r.path))   -- cycle guard
        )
        SELECT DISTINCT u.eid
        FROM reach JOIN unit u ON u.id = reach.unit_id
        WHERE reach.depth > 0
    """)
    rows = s.execute(
        sql, {"start_id": start_id, "types": list(rel_types),
              "as_of": as_of, "max_hops": max_hops}
    ).scalars().all()
    return sorted(rows)
