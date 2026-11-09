"""
⛔⛔⛔ SKETCH MINH HOẠ — SUPERSEDED. KHÔNG CODE/COPY TỪ FILE NÀY. ⛔⛔⛔
Đây là phác thảo illustrative, CÓ BUG ĐÃ BIẾT (materialize vô điều kiện, không
review_status, không applies_from, crash-on-overlap, in-place UPDATE phá tx-time).
NGUỒN CHÂN LÝ = docs/specs/w2-knowledge-graph.md §2–§3 + docs/specs/spec-audit-fixes.md
(Round-1/2/3). Member viết lại từ SPEC, không từ sketch này. (Chaos-audit đã tưởng
nhầm file này là impl thật → banner để không lặp.)

Logic hiệu lực-thời-gian (moat #1).

- reconstruct_as_of : văn bản của một Unit tại ngày T (và tùy chọn "như ta biết tại ngày K").
- document_as_of    : ghép cả văn bản (nhiều Unit) tại ngày T.
- apply_amendment   : áp một sửa đổi -> đóng phiên bản cũ, materialize phiên bản mới.
- repeal            : bãi bỏ -> tombstone.
- correct_amendment_date : sửa SAI ngày hiệu lực đã nhập (minh hoạ transaction-time).

Tương ứng Indigo: apply_amendment ~ Work.create_expression_at + Amendment.post_save;
reconstruct_as_of ~ documents.get_for_frbr_uri (expression_date__lte=T).
Khác Indigo: ở đây có trục transaction-time thật (tx_from/tx_to).
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import NormRelation, TX_INF, Unit, UnitVersion


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def reconstruct_as_of(
    session: Session,
    unit_id: int,
    as_of: dt.date,
    lang: str = "vi",
    known_as_of: Optional[dt.datetime] = None,
) -> Optional[str]:
    """Trả về text của Unit có hiệu lực tại ngày `as_of`.

    None => điều khoản KHÔNG tồn tại/đã bị bãi bỏ tại ngày đó (vắng mặt đúng).
    `known_as_of`: nếu đặt, truy theo tri thức hệ thống tại thời điểm đó (transaction-time).
    """
    know = known_as_of or _now()
    stmt = (
        select(UnitVersion)
        .where(UnitVersion.unit_id == unit_id)
        .where(UnitVersion.lang == lang)
        # valid-time: khoảng [valid_from, valid_to) chứa as_of
        .where(UnitVersion.valid_from <= as_of)
        .where((UnitVersion.valid_to.is_(None)) | (UnitVersion.valid_to > as_of))
        # transaction-time: bản ghi mà hệ thống tin tại thời điểm `know`
        .where(UnitVersion.tx_from <= know)
        .where(UnitVersion.tx_to > know)
    )
    v = session.scalars(stmt).one_or_none()
    if v is None or v.status == "repealed" or v.text is None:
        return None
    return v.text


def document_as_of(session: Session, document_id: int, as_of: dt.date, lang: str = "vi") -> str:
    """Ghép văn bản (các Unit theo thứ tự) tại ngày `as_of`. Bỏ qua điều đã bãi bỏ."""
    units = session.scalars(
        select(Unit).where(Unit.document_id == document_id).order_by(Unit.ordinal)
    ).all()
    parts: list[str] = []
    for u in units:
        txt = reconstruct_as_of(session, u.id, as_of, lang)
        if txt is not None:
            parts.append(f"{u.label}. {txt}")
    return "\n".join(parts)


def _open_version_at(session: Session, unit_id: int, on: dt.date, lang: str) -> Optional[UnitVersion]:
    """Phiên bản (theo tri thức hiện tại) đang có hiệu lực tại ngày `on`."""
    now = _now()
    return session.scalars(
        select(UnitVersion)
        .where(UnitVersion.unit_id == unit_id, UnitVersion.lang == lang)
        .where(UnitVersion.valid_from <= on)
        .where((UnitVersion.valid_to.is_(None)) | (UnitVersion.valid_to > on))
        .where(UnitVersion.tx_from <= now, UnitVersion.tx_to > now)
    ).one_or_none()


def apply_amendment(
    session: Session,
    target_unit_id: int,
    new_text: Optional[str],
    effective_date: dt.date,
    source_note: str,
    lang: str = "vi",
    status: str = "in_force",
    src_unit_id: Optional[int] = None,
    relation_type: str = "amends",
) -> UnitVersion:
    """Áp sửa đổi lên một Unit: đóng phiên bản cũ tại `effective_date`, mở phiên bản mới."""
    now = _now()
    prev = _open_version_at(session, target_unit_id, effective_date, lang)
    if prev is not None:
        prev.valid_to = effective_date  # đóng valid-time của bản cũ
    new_v = UnitVersion(
        unit_id=target_unit_id,
        lang=lang,
        valid_from=effective_date,
        valid_to=None,
        tx_from=now,
        tx_to=TX_INF,
        text=new_text,
        status=status,
        source_note=source_note,
    )
    session.add(new_v)
    if src_unit_id is not None:
        session.add(
            NormRelation(
                src_unit_id=src_unit_id,
                dst_unit_id=target_unit_id,
                relation_type=relation_type,
                effective_date=effective_date,
            )
        )
    session.flush()
    return new_v


def repeal(session: Session, target_unit_id: int, effective_date: dt.date,
           source_note: str, lang: str = "vi", src_unit_id: Optional[int] = None) -> UnitVersion:
    """Bãi bỏ một Unit kể từ `effective_date` (tombstone text=None)."""
    return apply_amendment(
        session, target_unit_id, None, effective_date, source_note,
        lang=lang, status="repealed", src_unit_id=src_unit_id, relation_type="repeals",
    )


def correct_amendment_date(
    session: Session, version_id: int, correct_valid_from: dt.date, lang: str = "vi"
) -> UnitVersion:
    """Minh hoạ TRANSACTION-TIME: ta nhập sai ngày hiệu lực, giờ sửa lại mà VẪN giữ được
    'trước đây hệ thống từng tin gì'. Đóng tx của bản ghi sai, chèn bản ghi đúng."""
    now = _now()
    wrong = session.get(UnitVersion, version_id)
    assert wrong is not None
    wrong.tx_to = now  # ngừng tin bản ghi cũ (nhưng vẫn lưu để audit)
    corrected = UnitVersion(
        unit_id=wrong.unit_id,
        lang=lang,
        valid_from=correct_valid_from,
        valid_to=wrong.valid_to,
        tx_from=now,
        tx_to=TX_INF,
        text=wrong.text,
        status=wrong.status,
        source_note=(wrong.source_note or "") + " [đã sửa ngày hiệu lực]",
    )
    session.add(corrected)
    session.flush()
    return corrected
