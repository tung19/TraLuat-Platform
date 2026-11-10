"""Chunker giữ-span (L4) — biên theo đơn vị cấu trúc, KHÔNG cắt mù độ dài.

Zero-drift (M1-fix): TÁCH `span_text` (nguyên văn, NEO trích dẫn — phải == KB
text@as_of) khỏi `embed_text` (có prepend struct_header — CHỈ để index/embed).
struct_header KHÔNG BAO GIỜ lẫn vào span dùng để khớp trích dẫn.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..w2 import repo
from ..w2.bitemporal import EffectStatus
from ..w2.models import Document, Unit
from ..w2.repo import _STRUCTURAL


@dataclass
class Chunk:
    unit_eid: str
    lang: str
    struct_header: str          # "{số hiệu} · Chương › Điều › Khoản" — KHÔNG neo citation
    span_text: str              # nguyên văn (neo) — == repo.citable_text(eid, as_of)
    effect_status: EffectStatus
    as_of: dt.date

    @property
    def embed_text(self) -> str:
        return f"{self.struct_header}\n{self.span_text}"  # chỉ để embed/BM25


def build_chunks(
    session: Session, frbr_uri: str, as_of: dt.date, lang: str = "vi",
) -> list[Chunk]:
    """Chunk mọi đơn vị NỘI DUNG của 1 VB tại as_of (keep-and-mark effect_status).

    Đơn vị kết cấu (Chương/Mục) → bỏ (chỉ là ngữ cảnh header). ABSENT → bỏ.
    """
    doc = session.scalar(sa.select(Document).where(Document.frbr_uri == frbr_uri))
    if doc is None:
        raise LookupError(f"document không tồn tại: {frbr_uri}")
    units = list(session.scalars(sa.select(Unit).where(Unit.document_id == doc.id)))
    by_id = {u.id: u for u in units}

    def _path(u: Unit) -> str:
        labels, cur = [], u
        while cur is not None:
            labels.append(cur.label)
            cur = by_id.get(cur.parent_id) if cur.parent_id else None
        return " › ".join(reversed(labels))

    head = doc.doc_number or doc.frbr_uri
    chunks: list[Chunk] = []
    for u in units:
        if u.unit_type in _STRUCTURAL:
            continue
        text, status = repo.citable_text(session, u.eid, as_of, lang)
        if text is None:  # ABSENT / không có bản trích được
            continue
        chunks.append(Chunk(
            unit_eid=u.eid, lang=lang, struct_header=f"{head} · {_path(u)}",
            span_text=text, effect_status=status, as_of=as_of,
        ))
    return chunks
