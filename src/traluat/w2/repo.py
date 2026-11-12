"""Repository bitemporal trên Postgres — cùng ngữ nghĩa engine thuần (slice-1),
nhưng bất biến no-overlap do DB (GiST EXCLUDE) gác, không do app.

apply_amendment chạy trong 1 transaction: đóng bản mở + chèn bản mới. Nếu tạo
chồng khoảng → Postgres RAISE (uv_no_overlap) — fail-loud ở tầng dữ liệu.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..core import legal_rule_base as lrb
from .bitemporal import BitemporalCorruption, EffectStatus
from .models import Document, NormRelation, Unit, UnitVersion

# Quan hệ auto-safe (không chi phối hiệu lforce): repeals/replaces/amends KHÔNG ở đây.
AUTO_SAFE_TYPES = {"cites", "guides", "hierarchy", "conflicts"}


def _unit_id(s: Session, eid: str) -> int:
    uid = s.scalar(sa.select(Unit.id).where(Unit.eid == eid))
    if uid is None:
        raise LookupError(f"unit eid không tồn tại: {eid}")
    return uid


def _db_now(s: Session) -> dt.datetime:
    """Transaction-time 'hiện tại' theo ĐỒNG HỒ DB (cùng nguồn với tx_from=now()).
    KHÔNG dùng datetime.now() của host: lệch đồng-hồ host↔DB (vd DB trong container
    chạy nhanh hơn) khiến `tx_from > known` → dòng vừa ghi bị ẩn (bitemporal sai)."""
    # clock_timestamp advances within a transaction, unlike now(). A request
    # that waited on a writer must not backdate its new belief before that row.
    return s.scalar(sa.select(sa.func.clock_timestamp()))


def reconstruct_as_of(
    s: Session, eid: str, as_of: dt.date, lang: str = "vi",
    known_as_of: dt.datetime | None = None,
) -> str | None:
    """Văn bản tại ngày T (SQL). None nếu vắng/bãi bỏ; raise nếu >1 dòng (hỏng)."""
    known = known_as_of or _db_now(s)
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

    def walk(parent_id: int | None, depth: int) -> list[str]:
        lines: list[str] = []
        for u in children.get(parent_id, []):
            descendant_lines = walk(u.id, depth + 1)
            if u.id in has_version:
                txt = reconstruct_as_of(s, u.eid, as_of, lang, known_as_of)
                if txt is not None:                       # in-force → in nội dung
                    lines.append(f"{'  ' * depth}{u.label}. {txt}")
                elif u.unit_type in _STRUCTURAL and descendant_lines:
                    # A future repeal tombstone does not erase a structural
                    # heading from earlier reconstructions of its children.
                    lines.append(f"{'  ' * depth}{u.label}")
            elif u.unit_type in _STRUCTURAL and descendant_lines:
                lines.append(f"{'  ' * depth}{u.label}")
            lines.extend(descendant_lines)
        return lines

    return "\n".join(walk(None, 0))


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
    # Lock the identity, not only existing version rows: even an empty/gapped
    # timeline must serialize concurrent writers before testing idempotency.
    s.execute(sa.select(Unit.id).where(Unit.id == uid).with_for_update())

    # idempotent
    if source_relation_id:
        exists = s.scalar(
            sa.select(sa.func.count())
            .select_from(UnitVersion)
            .where(
                UnitVersion.source_relation_id == source_relation_id,
                UnitVersion.unit_id == uid,
                UnitVersion.lang == lang,
                UnitVersion.valid_from == effective_date,
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

    now = _db_now(s)
    if covering:
        v = covering[0]
        if v.valid_from == effective_date and order_key < v.order_key:
            return
        new_to = v.valid_to
        # Transaction history is append-only: retire the old belief, then add
        # the corrected left segment and new segment at one database timestamp.
        v.tx_to = now
        s.flush()
        if v.valid_from < effective_date:
            s.add(UnitVersion(
                unit_id=uid, lang=lang, valid_from=v.valid_from, valid_to=effective_date,
                applies_from=v.applies_from, text=v.text, status=v.status,
                transitional=v.transitional, source_relation_id=v.source_relation_id,
                order_key=v.order_key, tx_from=now,
            ))
    else:
        new_to = s.scalar(sa.select(sa.func.min(UnitVersion.valid_from)).where(
            UnitVersion.unit_id == uid, UnitVersion.lang == lang,
            UnitVersion.tx_to.is_(None), UnitVersion.valid_from > effective_date,
        ))

    s.add(
        UnitVersion(
            unit_id=uid, lang=lang, valid_from=effective_date, valid_to=new_to,
            applies_from=applies_from, text=new_text, status=status,
            transitional=transitional, source_relation_id=source_relation_id,
            order_key=order_key,
            tx_from=now,
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


# ── Post-materialize hooks (ADR-0001) — projection đồ thị sync sau khi áp. ──
# repo KHÔNG import Neo4j; projector tự đăng ký hook (decoupled).
_POST_MATERIALIZE_HOOKS: list = []


def register_post_materialize(fn) -> None:
    _POST_MATERIALIZE_HOOKS.append(fn)


def clear_post_materialize_hooks() -> None:
    _POST_MATERIALIZE_HOOKS.clear()


def materialize(s: Session, rel: NormRelation, *, theta: float = 0.9) -> bool:
    """Áp một norm_relation vào kho bitemporal — CHỈ khi qua cổng.

    Cổng (C1): materialize khi `review_status='approved'`, HOẶC confidence≥θ cho
    loại AUTO-SAFE. repeals/replaces/amends **KHÔNG BAO GIỜ auto** (phải approved).
    Trả True nếu đã materialize, False nếu bị chặn (chờ duyệt). Sau khi áp → gọi
    post-materialize hooks (vd sync projection Neo4j) với cạnh vừa thay đổi.
    """
    if rel.id is not None:
        # Replays/concurrent approvals must not emit hooks twice.
        s.flush()
        s.refresh(rel, with_for_update=True)
    if rel.review_status == "rejected":
        return False
    approved = rel.review_status == "approved"
    auto_ok = rel.relation_type in AUTO_SAFE_TYPES and (rel.confidence or 0.0) >= theta
    if not (approved or auto_ok):
        return False  # chặn — chờ hàng đợi duyệt (không corrupt kho)

    if rel.relation_type not in AUTO_SAFE_TYPES | {"repeals", "replaces"}:
        # An amendment needs a reviewed replacement-text payload. A boolean
        # approval alone cannot synthesize that text or count as materialization.
        return False
    if rel.materialized_at is not None:
        return True
    if rel.relation_type in {"repeals", "replaces"}:
        _materialize_repeal(s, rel)
    rel.materialized_at = _db_now(s)
    s.flush()
    for hook in _POST_MATERIALIZE_HOOKS:        # sync projection (nếu đăng ký)
        hook(s, rel)
    return True


def _materialize_repeal(s: Session, rel: NormRelation) -> None:
    eff = rel.effective_date
    if eff is None:
        raise BitemporalCorruption(f"relation {rel.id}: repeals thiếu effective_date")
    if rel.dst_unit_id is not None:
        units = list(s.scalars(sa.select(Unit).where(Unit.document_id == rel.dst_doc_id)))
        children: dict[int | None, list[Unit]] = defaultdict(list)
        for unit in units:
            children[unit.parent_id].append(unit)
        by_id = {u.id: u for u in units}
        if rel.dst_unit_id not in by_id:
            raise BitemporalCorruption("relation đích unit/document không khớp")
        pending = [rel.dst_unit_id]
        target_units = []
        visited = set()
        while pending:
            uid = pending.pop()
            if uid in visited:
                raise BitemporalCorruption("chu trình cây unit")
            visited.add(uid)
            target_units.append(by_id[uid])
            pending.extend(child.id for child in children[uid])
    else:
        target_units = list(s.scalars(sa.select(Unit).where(Unit.document_id == rel.dst_doc_id)))
    for unit in sorted(target_units, key=lambda u: u.id):
        langs = list(s.scalars(sa.select(UnitVersion.lang).where(
            UnitVersion.unit_id == unit.id).distinct())) or ["vi"]
        for lang in langs:
            repeal(s, unit.eid, eff, source_relation_id=f"rel:{rel.id}",
                   lang=lang, order_key=rel.order_key)


# ── effect_status qua DB (B3-fix: enum, không bool) ─────────────────────────────
def effect_status(
    s: Session, eid: str, as_of: dt.date, lang: str = "vi",
    known_as_of: dt.datetime | None = None,
) -> EffectStatus:
    known = known_as_of or _db_now(s)
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


def citable_text(
    s: Session, eid: str, as_of: dt.date, lang: str = "vi",
    known_as_of: dt.datetime | None = None,
) -> tuple[str | None, EffectStatus]:
    """Nguyên văn DÙNG ĐỂ TRÍCH DẪN tại as_of + effect_status (keep-and-mark §1/§8).

    - IN_FORCE / TRANSITIONAL_APPLIES → bản đang áp (reconstruct_as_of).
    - EXPIRED_CITABLE → bản in-force CUỐI trước khi hết (vẫn trích được, kèm status).
    - NOT_YET → bản tương lai (để hiển thị + đánh dấu 'chưa hiệu lực').
    - ABSENT → (None, ABSENT).
    Tầng W3 tự hạ ưu tiên NOT_YET/EXPIRED khỏi 'thắng'; KHÔNG drop cứng.
    """
    known = known_as_of or _db_now(s)
    status = effect_status(s, eid, as_of, lang, known_as_of=known)
    if status == EffectStatus.IN_FORCE:
        return reconstruct_as_of(s, eid, as_of, lang, known_as_of=known), status
    if status == EffectStatus.ABSENT:
        return None, status
    # TRANSITIONAL_APPLIES: bản đã hết covering nhưng còn áp qua điều khoản chuyển
    # tiếp → cũng lấy bản in-force CUỐI trước as_of (reconstruct_as_of trả None).

    base = (
        sa.select(UnitVersion.text, UnitVersion.valid_from)
        .join(Unit, Unit.id == UnitVersion.unit_id)
        .where(
            Unit.eid == eid, UnitVersion.lang == lang, UnitVersion.text.is_not(None),
            UnitVersion.tx_from <= known,
            sa.or_(UnitVersion.tx_to.is_(None), known < UnitVersion.tx_to),
        )
    )
    if status == EffectStatus.NOT_YET:  # bản sớm nhất trong tương lai
        row = s.execute(
            base.where(UnitVersion.valid_from > as_of)
            .order_by(UnitVersion.valid_from.asc()).limit(1)
        ).first()
    else:  # EXPIRED_CITABLE: bản in-force cuối trước mốc
        row = s.execute(
            base.where(UnitVersion.valid_from <= as_of)
            .order_by(UnitVersion.valid_from.desc()).limit(1)
        ).first()
    return (row[0] if row else None), status


_DESTRUCTIVE = ("repeals", "replaces", "amends")


def pending_destructive_relation(s: Session, eid: str) -> bool:
    """R3: unit (hoặc văn bản chứa nó) đang là ĐÍCH của quan hệ repeals/replaces/
    amends CHƯA DUYỆT (needs_review) → điều có thể đã chết mà queue chưa áp. Caller
    hạ caveat. Tránh trả lời chắc nịch trên điều sắp bị thay đổi."""
    uid = s.scalar(sa.select(Unit.id).where(Unit.eid == eid))
    if uid is None:
        return False
    doc_id = s.scalar(sa.select(Unit.document_id).where(Unit.id == uid))
    n = s.scalar(
        sa.select(sa.func.count()).select_from(NormRelation).where(
            NormRelation.relation_type.in_(_DESTRUCTIVE),
            NormRelation.review_status.in_(("needs_review", "approved")),
            NormRelation.materialized_at.is_(None),
            sa.or_(NormRelation.dst_unit_id == uid, NormRelation.dst_doc_id == doc_id),
        )
    )
    return bool(n)


# ── R5: correct_valid_from (tx-time — giữ 'điều hệ thống từng tin') ───────────────
def correct_valid_from(
    s: Session, version_id: int, correct_valid_from: dt.date,
    now: dt.datetime | None = None,
) -> None:
    """Sửa ngày hiệu lực bị NHẬP SAI — KHÔNG ghi đè (chaos: in-place UPDATE phá tx-time).

    Đóng bản sai ở trục transaction-time (tx_to=now, giữ để audit) + chèn bản ĐÚNG
    (tx_from=now). → truy vấn với known_as_of trong quá khứ vẫn trả điều hệ-thống-từng-tin.
    """
    s.execute(sa.select(Unit.id).join(UnitVersion).where(
        UnitVersion.id == version_id).with_for_update(of=Unit))
    v = s.get(UnitVersion, version_id, populate_existing=True, with_for_update=True)
    if v is None or v.tx_to is not None:
        raise BitemporalCorruption(f"version {version_id} không tồn tại / không còn current")
    now = now or _db_now(s)
    if now < v.tx_from:
        raise BitemporalCorruption("transaction-time không được đi lùi")
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
    *, rank_fn=None,
) -> ConflictResult:
    """Giải tập điều ĐÃ-được-flag là chọi nhau. KHÔNG tự phát hiện (đó là FR-41).

    ① Cổng hiệu lực (effect_status@as_of): hết hiệu lực → cite nhưng KHÔNG tranh thắng.
    ② lex superior (authority_rank@as_of, rule base) → ③ lex posterior (cùng rank, mới hơn)
    → ④ hoà / rank mơ hồ / không-in-force → ABSTAIN→human.

    rank_fn(doc_type, as_of)→int|None: bơm thang bậc theo vùng tài phán (W6
    JurisdictionPack — portability nước thứ 2). Mặc định = legal_rule_base VN.
    """
    rank_fn = rank_fn or lrb.rank_of
    items = []
    for eid in eids:
        row = s.execute(
            sa.select(Document.doc_type, Document.date_effective, Document.date_issued,
                      Document.authority_id)
            .join(Unit, Unit.document_id == Document.id).where(Unit.eid == eid)
        ).first()
        if row is None:
            raise LookupError(f"unit eid không tồn tại: {eid}")
        st = effect_status(s, eid, as_of)
        items.append({
            "eid": eid, "doc_type": row.doc_type, "date_effective": row.date_effective,
            "date_issued": row.date_issued, "authority_id": row.authority_id,
            "status": st, "rank": rank_fn(row.doc_type, as_of),
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
    dates = [it["date_issued"] for it in top]
    authorities = {it["authority_id"] for it in top}
    if (len(authorities) == 1 and None not in authorities
            and all(d is not None for d in dates) and len(set(dates)) == len(dates)):
        w = max(top, key=lambda it: it["date_issued"])
        return ConflictResult(w["eid"], losers_except(w["eid"]), "lex_posterior",
                              "Cùng cơ quan và rank → ban hành sau thắng.")

    # ④ hoà / posterior⟂specialis → ABSTAIN (principle #6)
    return ConflictResult(None, all_losers, "abstain:tie",
                          "Cùng rank không phân định (posterior⟂specialis/cùng ngày) → human.",
                          unresolved=True)


# ── Neighborhood: subgraph quanh 1 điều (cho visualize FR-37) ────────────────────
def neighborhood(
    s: Session, eid: str, as_of: dt.date | None = None,
    rel_types: list[str] | None = None, max_hops: int = 1,
) -> dict:
    """Trả {center, nodes, edges} — đồ thị lân cận (cả 2 chiều) tới max_hops, lọc
    hiệu lực cạnh theo as_of. Nodes = unit (eid/label/type); edges = quan hệ có hướng."""
    as_of = as_of or dt.date.max
    if not 0 <= max_hops <= 3:
        raise ValueError("max_hops phải trong khoảng 0..3")
    frontier = {_unit_id(s, eid)}
    seen_ids = set(frontier)
    rels: dict[int, NormRelation] = {}
    for _ in range(max_hops):
        if not frontier:
            break
        q = sa.select(NormRelation).where(
            NormRelation.review_status == "approved",
            sa.or_(NormRelation.src_unit_id.in_(frontier),
                   NormRelation.dst_unit_id.in_(frontier)),
            sa.or_(NormRelation.effective_date.is_(None),
                   NormRelation.effective_date <= as_of))
        if rel_types:
            q = q.where(NormRelation.relation_type.in_(rel_types))
        nxt = set()
        for r in s.scalars(q):
            if r.src_unit_id is None or r.dst_unit_id is None:
                continue
            rels[r.id] = r
            for nid in (r.src_unit_id, r.dst_unit_id):
                if nid not in seen_ids:
                    seen_ids.add(nid); nxt.add(nid)
        frontier = nxt

    units = {u.id: u for u in s.scalars(sa.select(Unit).where(Unit.id.in_(seen_ids)))}
    nodes = [{"eid": u.eid, "label": u.label, "type": u.unit_type} for u in units.values()]
    edges = [{"src": units[r.src_unit_id].eid, "dst": units[r.dst_unit_id].eid,
              "type": r.relation_type, "review_status": r.review_status}
             for r in rels.values()
             if r.src_unit_id in units and r.dst_unit_id in units]
    return {"center": eid, "nodes": nodes, "edges": edges}


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
    if not 0 <= max_hops <= 3:
        raise ValueError("max_hops phải trong khoảng 0..3")
    as_of = as_of or dt.date.max
    sql = sa.text("""
        WITH RECURSIVE reach(unit_id, depth, path) AS (
            SELECT CAST(:start_id AS integer), 0, ARRAY[CAST(:start_id AS integer)]
          UNION ALL
            SELECT nr.dst_unit_id, r.depth + 1, r.path || nr.dst_unit_id
            FROM reach r
            JOIN norm_relation nr ON nr.src_unit_id = r.unit_id
            WHERE nr.relation_type = ANY(CAST(:types AS text[]))
              AND nr.review_status = 'approved'
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
