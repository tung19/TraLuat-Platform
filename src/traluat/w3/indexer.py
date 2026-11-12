"""L4 reindex — dựng/ cập nhật bảng `chunk` (index phái sinh) TỪ L3 bitemporal.

Bất biến: L4 rebuild được từ L3, KHÔNG phải nguồn-sự-thật-thứ-2. Embed theo LÔ lúc
reindex (data-plane §6.3, không per-query). Idempotent upsert theo (eid,lang,
source_version,namespace). Mỗi UnitVersion current-belief (tx_to NULL, có text) → 1
chunk với [valid_from,valid_to) denormalized → push-down as_of trong SQL.
"""

from __future__ import annotations

import math

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..w2.models import Chunk, Document, Unit, UnitVersion


def embedding_identity(embedder) -> str:
    return getattr(embedder, "model_id", None) or (
        f"{type(embedder).__module__}.{type(embedder).__qualname__}:{embedder.dim}")


def validate_vectors(vectors, count):
    if len(vectors) != count or any(
        len(v) != 1024 or not all(math.isfinite(x) for x in v) or not any(v)
        for v in vectors
    ):
        raise ValueError("expected one finite, nonzero 1024-dimensional vector per input")


def _paths(session: Session, doc_id: int) -> dict[int, str]:
    units = list(session.scalars(sa.select(Unit).where(Unit.document_id == doc_id)))
    by_id = {u.id: u for u in units}

    def path(u: Unit) -> str:
        labels, cur = [], u
        while cur is not None:
            labels.append(cur.label)
            cur = by_id.get(cur.parent_id) if cur.parent_id else None
        return " › ".join(reversed(labels))

    return {u.id: path(u) for u in units}


def reindex_document(
    session: Session, frbr_uri: str, *, embedder=None, namespace: str = "kb",
    lang: str = "vi",
) -> int:
    """(Re)index mọi version current-belief của 1 VB → bảng chunk. Trả số chunk."""
    doc = session.scalar(sa.select(Document).where(Document.frbr_uri == frbr_uri))
    if doc is None:
        raise LookupError(f"document không tồn tại: {frbr_uri}")
    head = doc.doc_number or doc.frbr_uri
    paths = _paths(session, doc.id)

    rows = session.execute(
        sa.select(Unit.id, Unit.eid, UnitVersion.valid_from, UnitVersion.valid_to,
                  UnitVersion.text)
        .join(UnitVersion, UnitVersion.unit_id == Unit.id)
        .where(Unit.document_id == doc.id, UnitVersion.lang == lang,
               UnitVersion.tx_to.is_(None), UnitVersion.text.is_not(None))
    ).all()
    embs = embedder.embed([r.text for r in rows]) if embedder is not None and rows else [None] * len(rows)
    if embedder is not None:
        validate_vectors(embs, len(rows))
    # Validate model output before replacing the old index. Empty documents
    # still remove stale chunks; transaction ownership remains with the caller.
    session.execute(sa.delete(Chunk).where(
        Chunk.namespace == namespace, Chunk.lang == lang,
        Chunk.unit_id.in_(sa.select(Unit.id).where(Unit.document_id == doc.id))))
    n = 0
    for r, emb in zip(rows, embs):
        sv = r.valid_from.isoformat()           # version-stamp phân biệt bản theo thời gian
        payload = {
            "unit_id": r.id, "eid": r.eid, "lang": lang, "namespace": namespace,
            "struct_header": f"{head} · {paths.get(r.id, r.eid)}",
            "span_text": r.text, "char_from": 0, "char_to": len(r.text),
            "valid_from": r.valid_from, "valid_to": r.valid_to,
            "source_version": sv, "embedding": emb,
            "embedding_model": embedding_identity(embedder) if embedder is not None else None,
        }
        stmt = pg_insert(Chunk).values(**payload)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_chunk_ver",
            set_={"span_text": payload["span_text"], "struct_header": payload["struct_header"],
                  "valid_to": payload["valid_to"], "char_to": payload["char_to"],
                  "embedding": emb, "embedding_model": payload["embedding_model"]},
        )
        session.execute(stmt)
        n += 1
    session.flush()
    return n
