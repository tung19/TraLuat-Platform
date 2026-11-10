"""Stage 6 — handoff W1 → W2: nạp cây ParsedUnit vào Document/Unit/UnitVersion.

W2 sở hữu bitemporal; W1 chỉ cung cấp bản gốc. valid_from = date_effective của
văn bản (phased-commencement cấp Điều: dùng unit.effective_date khi có — thêm sau).
"""

from __future__ import annotations

import datetime as dt

import sqlalchemy as sa

from ..w2.models import Document, NormRelation, Unit, UnitVersion
from .relations import RelationCandidate, extract_relations
from .structure import ParsedUnit, parse_structure


def build_ingest(text: str, doc_slug: str) -> list[ParsedUnit]:
    """Parse văn bản → cây ParsedUnit (stage 3)."""
    return parse_structure(text, doc_slug)


def load_to_w2(
    session,
    *,
    frbr_uri: str,
    doc_type: str,
    date_effective: dt.date,
    units: list[ParsedUnit],
    doc_number: str | None = None,
    lang: str = "vi",
) -> Document:
    """Ghi Document + Unit (cây) + UnitVersion (bản gốc, valid_from=date_effective)."""
    doc = Document(
        frbr_uri=frbr_uri, doc_number=doc_number, doc_type=doc_type,
        date_effective=date_effective, status="con_hieu_luc",
    )
    session.add(doc)
    session.flush()

    eid_to_id: dict[str, int] = {}
    for u in units:  # thứ tự tài liệu → cha trước con
        parent_id = eid_to_id.get(u.parent_eid) if u.parent_eid else None
        unit = Unit(
            document_id=doc.id, parent_id=parent_id, unit_type=u.unit_type,
            ordinal=u.ordinal, label=u.label, eid=u.eid,
        )
        session.add(unit)
        session.flush()
        eid_to_id[u.eid] = unit.id
        if u.text:  # chỉ đơn vị NỘI DUNG có version (kết cấu → không)
            session.add(UnitVersion(
                unit_id=unit.id, lang=lang, valid_from=date_effective, valid_to=None,
                text=u.text, status="con_hieu_luc",
            ))
    session.flush()
    return doc


def _resolve_dst_unit(session, dst_doc_id: int, dieu: int) -> int | None:
    """Điều N của VB đích → unit.id (unit_type='dieu', ordinal=N)."""
    return session.scalar(
        sa.select(Unit.id).where(
            Unit.document_id == dst_doc_id, Unit.unit_type == "dieu", Unit.ordinal == dieu,
        )
    )


def load_relations_to_w2(
    session,
    *,
    src_frbr_uri: str,
    candidates: list[RelationCandidate],
    default_effective_date: dt.date | None = None,
) -> tuple[list[NormRelation], list[RelationCandidate]]:
    """Nạp RelationCandidate → norm_relation (review_status='needs_review').

    Trả (đã tạo, chưa giải được). KHÔNG materialize — chỉ xếp vào hàng đợi duyệt;
    materialize gate (W2) mới chạm kho bitemporal. VB đích chưa có trong kho →
    'chưa giải được' (không bịa FK), chờ VB kia ingest rồi chạy lại.
    """
    src = session.scalar(sa.select(Document).where(Document.frbr_uri == src_frbr_uri))
    if src is None:
        raise ValueError(f"src_frbr_uri không có trong kho: {src_frbr_uri}")

    created: list[NormRelation] = []
    unresolved: list[RelationCandidate] = []
    seen: set[tuple] = set()
    for c in candidates:
        dst = session.scalar(
            sa.select(Document).where(Document.doc_number == c.dst_doc_number)
        )
        if dst is None:
            unresolved.append(c)  # VB đích chưa ingest — chờ, không bịa
            continue
        dst_unit_id = _resolve_dst_unit(session, dst.id, c.dst_dieu) if c.dst_dieu else None
        eff = c.effective_date or default_effective_date
        key = (src.id, dst.id, dst_unit_id, c.relation_type, eff)
        if key in seen:  # chống nhân đôi trong cùng mẻ (DB còn nr_dedupe)
            continue
        seen.add(key)
        rel = NormRelation(
            relation_type=c.relation_type, effective_date=eff,
            src_doc_id=src.id, src_unit_id=None,
            dst_doc_id=dst.id, dst_unit_id=dst_unit_id,
            confidence=c.confidence, confidence_basis=c.confidence_basis,
            review_status="needs_review", evidence_span=c.evidence_span,
        )
        session.add(rel)
        created.append(rel)
    session.flush()
    return created, unresolved


def extract_and_load_relations(
    session, *, src_frbr_uri: str, text: str, default_effective_date: dt.date | None = None,
) -> tuple[list[NormRelation], list[RelationCandidate]]:
    """Tiện ích: trích cue-phrase từ `text` rồi nạp vào hàng đợi duyệt."""
    cands = extract_relations(text)
    return load_relations_to_w2(
        session, src_frbr_uri=src_frbr_uri, candidates=cands,
        default_effective_date=default_effective_date,
    )
