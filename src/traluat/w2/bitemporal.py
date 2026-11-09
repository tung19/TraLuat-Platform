"""Bitemporal core — reconstruct 'văn bản tại ngày T' (moat #1).

Pure-Python logic layer (slice-1). The Postgres/SQLAlchemy repository (slice-2)
will WRAP this: same semantics, plus the GiST EXCLUDE constraint + SERIALIZABLE
apply as DB-enforced invariants (engineering-principles #2).

Spec: docs/specs/w2-knowledge-graph.md §2–§3 + docs/specs/spec-audit-fixes.md.
Audit fixes embedded:
  - half-open [valid_from, valid_to)  (no off-by-one)
  - effect_status ENUM, not bool      (B3-fix)
  - applies_from for retroactivity     (A-fix; distinct from valid_from)
  - same-date fold via order_key       (G4-fix)
  - idempotent apply via source_relation_id (chaos C1)
  - >1 in-force row ⇒ raise (fail-loud, not silent) (chaos C2 / §11)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum


class EffectStatus(str, Enum):
    IN_FORCE = "in_force"
    EXPIRED_CITABLE = "expired_citable"          # hết hiệu lực, vẫn trích dẫn
    TRANSITIONAL_APPLIES = "transitional_applies"  # chuyển tiếp: luật cũ còn áp
    NOT_YET = "not_yet"                           # chưa tới ngày hiệu lực
    ABSENT = "absent"                             # không tồn tại version nào


class BitemporalCorruption(Exception):
    """Bất biến bitemporal bị vi phạm (vd >1 dòng in-force cùng as_of)."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class UnitVersion:
    """Một phiên bản của một đơn vị (Điều/Khoản/Điểm) — bitemporal 2 trục."""

    unit_eid: str
    lang: str
    valid_from: date
    valid_to: date | None            # None = mở (+∞) — half-open: [valid_from, valid_to)
    text: str | None                 # None = tombstone (bãi bỏ)
    tx_from: datetime = field(default_factory=_utcnow)
    tx_to: datetime | None = None    # None = điều hệ thống ĐANG tin
    applies_from: date | None = None  # ★ hồi tố: áp cho hành vi TỪ ngày này (có thể < valid_from)
    status: str = "con_hieu_luc"
    transitional: bool = False
    source_relation_id: str | None = None
    order_key: int = 0               # ★ thứ tự intra-date = (date_issued, gazette)

    @property
    def eff_applies_from(self) -> date:
        return self.applies_from if self.applies_from is not None else self.valid_from


# ── predicates ────────────────────────────────────────────────────────────────
def _covers_valid(v: UnitVersion, as_of: date) -> bool:
    """Half-open [valid_from, valid_to) — tại biên, bản cũ đóng / bản mới mở."""
    return v.valid_from <= as_of and (v.valid_to is None or as_of < v.valid_to)


def _current_belief(v: UnitVersion, known: datetime) -> bool:
    return v.tx_from <= known and (v.tx_to is None or known < v.tx_to)


def _rows_for(versions, unit_eid, lang, known):
    return [
        v for v in versions
        if v.unit_eid == unit_eid and v.lang == lang and _current_belief(v, known)
    ]


# ── R1: reconstruct_as_of ───────────────────────────────────────────────────────
def reconstruct_as_of(
    versions: list[UnitVersion],
    unit_eid: str,
    as_of: date,
    lang: str = "vi",
    known_as_of: datetime | None = None,
) -> str | None:
    """Văn bản của một đơn vị tại ngày T (và tùy chọn 'như hệ thống tin tại ngày K').

    Trả None nếu vắng mặt / bị bãi bỏ. Raise nếu >1 dòng in-force (dữ liệu hỏng).
    """
    known = known_as_of or _utcnow()
    rows = [v for v in _rows_for(versions, unit_eid, lang, known) if _covers_valid(v, as_of)]
    if len(rows) > 1:
        raise BitemporalCorruption(
            f"{unit_eid}@{as_of}: {len(rows)} dòng in-force (valid-time chồng nhau)"
        )
    if not rows:
        return None
    return rows[0].text  # None nếu tombstone


# ── effect_status (B3-fix: enum, không bool) ────────────────────────────────────
def effect_status(
    versions: list[UnitVersion],
    unit_eid: str,
    as_of: date,
    lang: str = "vi",
    known_as_of: datetime | None = None,
) -> EffectStatus:
    known = known_as_of or _utcnow()
    rows = _rows_for(versions, unit_eid, lang, known)
    if not rows:
        return EffectStatus.ABSENT
    covering = [v for v in rows if _covers_valid(v, as_of)]
    if len(covering) > 1:
        raise BitemporalCorruption(f"{unit_eid}@{as_of}: {len(covering)} dòng in-force")
    if covering:
        v = covering[0]
        # tombstone phủ as_of = đã bãi bỏ (hết hiệu lực, vẫn cite)
        return EffectStatus.EXPIRED_CITABLE if v.text is None else EffectStatus.IN_FORCE
    # không phủ: trước ngày sớm nhất = chưa hiệu lực; sau = hết (hoặc chuyển tiếp)
    earliest = min(v.valid_from for v in rows)
    if as_of < earliest:
        return EffectStatus.NOT_YET
    if any(v.transitional for v in rows):
        return EffectStatus.TRANSITIONAL_APPLIES
    return EffectStatus.EXPIRED_CITABLE


# ── governing law for an ACT (A-fix: dùng applies_from cho hồi tố) ───────────────
def governing_candidates(
    versions: list[UnitVersion],
    unit_eid: str,
    act_date: date,
    lang: str = "vi",
    known_as_of: datetime | None = None,
) -> list[UnitVersion]:
    """MỌI phiên bản có thể điều chỉnh một hành vi xảy ra tại act_date.

    Gồm: (a) bản đang in-force LÚC act_date (valid-time), VÀ (b) mọi luật SAU có
    `applies_from <= act_date` (hồi tố, phủ ngược). Dùng [eff_applies_from, valid_to).

    ★ A-fix / principle #6: hàm này chỉ RETRIEVE ứng viên — KHÔNG chọn cái thắng.
    Lex-mitior (chọn bản CÓ LỢI cho đối tượng) là quyết định của tầng
    legal-rule-base, chạy NGOÀI đây. Trả nhiều bản = đúng (để so favorability).
    Sắp theo valid_from (bản ban hành sau đứng cuối).
    """
    known = known_as_of or _utcnow()
    cands = [
        v for v in _rows_for(versions, unit_eid, lang, known)
        if v.eff_applies_from <= act_date and (v.valid_to is None or act_date < v.valid_to)
    ]
    return sorted(cands, key=lambda v: v.valid_from)


# ── R3/R4: apply_amendment / repeal ─────────────────────────────────────────────
def apply_amendment(
    versions: list[UnitVersion],
    target_eid: str,
    new_text: str | None,
    effective_date: date,
    *,
    source_relation_id: str | None = None,
    order_key: int = 0,
    applies_from: date | None = None,
    lang: str = "vi",
    status: str = "con_hieu_luc",
    transitional: bool = False,
    now: datetime | None = None,
) -> list[UnitVersion]:
    """Áp một sửa đổi: đóng bản mở tại effective_date + chèn bản mới.

    - Idempotent theo source_relation_id (replay không nhân đôi) — chaos C1.
    - Same-date: fold theo order_key (không tạo [d, d) zero-width) — G4-fix.
    - Fail-loud nếu tạo valid-time chồng nhau — chaos C2.
    ★ slice-3: INTERVAL-SPLIT — xử cả sửa-đổi-lệch-thứ-tự lọt GIỮA một khoảng đã
    đóng. Tìm bản phủ effective_date (mở hoặc đóng), cắt tại đó: bản cũ valid_to=eff,
    bản mới [eff, old_to). Khoảng sau (nếu có) giữ nguyên.
    """
    now = now or _utcnow()

    # idempotent
    if source_relation_id and any(
        v.source_relation_id == source_relation_id
        and v.valid_from == effective_date
        and v.tx_to is None
        for v in versions
    ):
        return versions

    current = [
        v for v in versions
        if v.unit_eid == target_eid and v.lang == lang and v.tx_to is None
    ]
    covering = [v for v in current if _covers_valid(v, effective_date)]
    if len(covering) > 1:
        raise BitemporalCorruption(f"{target_eid}@{effective_date}: {len(covering)} bản phủ")

    if covering:
        v = covering[0]
        if v.valid_from == effective_date:  # same-date fold theo order_key
            if order_key >= v.order_key:
                v.text, v.status, v.order_key = new_text, status, order_key
                v.source_relation_id = source_relation_id
                v.applies_from, v.transitional = applies_from, transitional
            return versions
        old_to = v.valid_to          # có thể None (tail mở) hoặc date (giữa chuỗi)
        v.valid_to = effective_date  # cắt
        new_to = old_to
    else:
        new_to = None                # không bản nào phủ: segment mới mở

    versions.append(
        UnitVersion(
            unit_eid=target_eid, lang=lang, valid_from=effective_date, valid_to=new_to,
            text=new_text, tx_from=now, tx_to=None, applies_from=applies_from,
            status=status, transitional=transitional,
            source_relation_id=source_relation_id, order_key=order_key,
        )
    )
    _assert_no_overlap(versions, target_eid, lang)
    return versions


def repeal(versions, target_eid, effective_date, **kw) -> list[UnitVersion]:
    """R4: bãi bỏ = apply_amendment với text=None, status='het_hieu_luc'."""
    kw.setdefault("status", "het_hieu_luc")
    return apply_amendment(versions, target_eid, None, effective_date, **kw)


def _assert_no_overlap(versions, unit_eid, lang) -> None:
    open_rows = sorted(
        (v for v in versions if v.unit_eid == unit_eid and v.lang == lang and v.tx_to is None),
        key=lambda v: v.valid_from,
    )
    for prev, cur in zip(open_rows, open_rows[1:]):
        if prev.valid_to is None or cur.valid_from < prev.valid_to:
            raise BitemporalCorruption(
                f"{unit_eid}: khoảng valid-time chồng nhau "
                f"[{prev.valid_from},{prev.valid_to}) vs [{cur.valid_from},{cur.valid_to})"
            )
