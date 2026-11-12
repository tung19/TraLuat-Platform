"""Stage 6 — handoff W1 → W2: nạp cây ParsedUnit vào Document/Unit/UnitVersion.

W2 sở hữu bitemporal; W1 chỉ cung cấp bản gốc. valid_from = date_effective của
văn bản (phased-commencement cấp Điều: dùng unit.effective_date khi có — thêm sau).
"""

from __future__ import annotations

import datetime as dt
import hashlib
from urllib.parse import quote

import sqlalchemy as sa

from ..w2.models import Authority, Document, NormRelation, Unit, UnitVersion
from .metadata import DocMeta, extract_effective_overrides, extract_metadata
from .relations import RelationCandidate, extract_relations
from .structure import ParsedUnit, parse_structure

# doc_type canonical → segment FRBR
_TYPE_SEG = {
    "nghi_dinh": "nd", "luat": "luat", "thong_tu": "tt",
    "quyet_dinh": "qd", "nghi_quyet": "nq", "phap_lenh": "pl",
}


def derive_frbr_uri(meta: DocMeta) -> str | None:
    """'99/2020/NĐ-CP' + nghi_dinh → 'trl:vn/nd/99/2020'. Thiếu dữ kiện → None."""
    if not (meta.doc_number and meta.doc_type):
        return None
    seg = _TYPE_SEG.get(meta.doc_type)
    parts = meta.doc_number.split("/")
    if seg is None or len(parts) != 3 or not all(parts):
        return None
    base = f"trl:vn/{seg}/{parts[0]}/{parts[1]}"
    # Circulars/decisions/resolutions from different issuers share numbers and
    # years. Retain the complete suffix, preserving legacy national-law/ND URIs.
    if meta.doc_type not in {"nghi_dinh", "luat"}:
        base += "/" + quote(parts[2].casefold(), safe="-")
    return base


def _resolve_authority(session, name: str | None) -> int | None:
    if not name:
        return None
    aid = session.scalar(sa.select(Authority.id).where(Authority.name == name))
    if aid is None:
        auth = Authority(name=name)
        session.add(auth)
        session.flush()
        aid = auth.id
    return aid


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
    date_issued: dt.date | None = None,
    authority_id: int | None = None,
    effective_overrides: dict[str, dt.date] | None = None,
    source_hash: str | None = None,
    lang: str = "vi",
) -> Document:
    """Ghi Document + Unit (cây) + UnitVersion (bản gốc, valid_from=date_effective).

    effective_overrides {eid: ngày} = phased-commencement: đơn vị (và con của nó)
    lấy valid_from riêng; override cụ thể nhất (eid dài nhất khớp) thắng.
    """
    ov = effective_overrides or {}

    def _valid_from(eid: str) -> dt.date:
        best: tuple[str, dt.date] | None = None
        for k, when in ov.items():
            if (eid == k or eid.startswith(k + "__")) and (best is None or len(k) > len(best[0])):
                best = (k, when)
        return best[1] if best else date_effective

    doc = Document(
        frbr_uri=frbr_uri, doc_number=doc_number, doc_type=doc_type,
        date_issued=date_issued, date_effective=date_effective,
        authority_id=authority_id, status="con_hieu_luc", source_hash=source_hash,
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
                unit_id=unit.id, lang=lang, valid_from=_valid_from(u.eid), valid_to=None,
                text=u.text, status="con_hieu_luc",
            ))
    session.flush()
    return doc


def ingest_document(
    session,
    text: str,
    doc_slug: str,
    *,
    frbr_uri: str | None = None,
    doc_type: str | None = None,
    date_effective: dt.date | None = None,
    doc_number: str | None = None,
    lang: str = "vi",
) -> tuple[Document, DocMeta]:
    """Toàn trình W1: text → metadata + structure → W2 (không cần truyền tay).

    Trường truyền tay (nếu có) GHI ĐÈ metadata trích tự động — người > máy. Thiếu
    frbr_uri/doc_type/date_effective sau khi gộp → lỗi rõ ràng (không ingest nửa vời).
    """
    meta = extract_metadata(text)
    frbr_uri = frbr_uri or derive_frbr_uri(meta)
    doc_type = doc_type or meta.doc_type
    doc_number = doc_number or meta.doc_number
    date_effective = date_effective or meta.date_effective

    missing = [n for n, v in
               (("frbr_uri", frbr_uri), ("doc_type", doc_type), ("date_effective", date_effective))
               if v is None]
    if missing:
        raise ValueError(f"metadata thiếu, không ingest: {', '.join(missing)} (doc_slug={doc_slug})")

    source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    # Replay is safe only when identity AND content agree. A corrected source is
    # a knowledge-ops review/versioning operation, never a silently ignored blob.
    session.execute(sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:uri, 0))"),
                    {"uri": frbr_uri})
    existing = session.scalar(sa.select(Document).where(Document.frbr_uri == frbr_uri))
    if existing is not None:
        if (existing.doc_number != doc_number or existing.doc_type != doc_type
                or existing.source_hash != source_hash):
            raise ValueError(f"FRBR đã tồn tại với nguồn/định danh khác, cần duyệt: {frbr_uri}")
        return existing, meta

    units = build_ingest(text, doc_slug)
    if not units:
        raise ValueError(f"không tìm thấy cấu trúc pháp lý để nạp: {doc_slug}")
    authority_id = _resolve_authority(session, meta.authority_name)
    doc = load_to_w2(
        session, frbr_uri=frbr_uri, doc_type=doc_type, date_effective=date_effective,
        units=units, doc_number=doc_number, source_hash=source_hash,
        date_issued=meta.date_issued, authority_id=authority_id,
        effective_overrides=extract_effective_overrides(text, doc_slug), lang=lang,
    )
    return doc, meta


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
    session.execute(sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": f"norm-relations:{src.id}"})

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
        if c.dst_dieu is not None and dst_unit_id is None:
            unresolved.append(c)
            continue
        eff = c.effective_date or default_effective_date
        key = (src.id, dst.id, dst_unit_id, c.relation_type, eff)
        if key in seen:  # chống nhân đôi trong cùng mẻ (DB còn nr_dedupe)
            continue
        seen.add(key)
        existing = session.scalar(sa.select(NormRelation).where(
            NormRelation.src_doc_id == src.id,
            NormRelation.src_unit_id.is_(None),
            NormRelation.dst_doc_id == dst.id,
            NormRelation.dst_unit_id.is_not_distinct_from(dst_unit_id),
            NormRelation.relation_type == c.relation_type,
            NormRelation.effective_date.is_not_distinct_from(eff),
        ))
        if existing is not None:
            # Preserve an expert's approved/rejected decision on CDC replay.
            continue
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
