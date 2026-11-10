"""RetrievalService (L5) — slice-1: lexical keep-and-MARK, hiệu-lực-aware.

★ keep-and-MARK (§1 / principle #4): KHÔNG drop cứng theo hiệu lực. Mỗi ứng viên
mang effect_status@as_of; EXPIRED_CITABLE/TRANSITIONAL vẫn trả (kèm nhãn), chỉ
HẠ ưu tiên khỏi 'thắng'; NOT_YET đánh dấu 'chưa hiệu lực'.

⚠️ Slice-1 dùng chấm điểm LEXICAL tất định (overlap token) làm chỗ-giữ. Defer:
BM25 tiếng Việt + dense bge-m3 (1024d) + RRF + cross-encoder rerank (§1, build#2).
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..w2.bitemporal import EffectStatus
from ..w2.models import Chunk as ChunkRow, Document
from .chunker import Chunk, build_chunks

_APPLICABLE = {EffectStatus.IN_FORCE, EffectStatus.TRANSITIONAL_APPLIES}
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(unicodedata.normalize("NFC", text).lower()))


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float
    applicable: bool            # effect_status ∈ {IN_FORCE, TRANSITIONAL_APPLIES}

    @property
    def effect_status(self) -> EffectStatus:
        return self.chunk.effect_status

    @property
    def unit_eid(self) -> str:
        return self.chunk.unit_eid


def retrieve(
    session: Session,
    query: str,
    as_of: dt.date,
    *,
    lang: str = "vi",
    scope_frbr_uris: list[str] | None = None,
    top_k: int = 8,
    embedder=None,
    known_as_of: dt.datetime | None = None,
) -> list[RetrievedChunk]:
    """Trả top_k ứng viên cấp điều–khoản, mỗi cái gắn effect_status@as_of.

    scope None → mọi VB trong kho. Sắp: ÁP-DỤNG-ĐƯỢC trước, rồi điểm cao hơn, rồi eid.
    - embedder None → lexical overlap token (chỉ giữ ứng viên có overlap > 0).
    - embedder (Embedder, vd BgeM3Embedder) → DENSE cosine (giữ MỌI ứng viên, kể cả
      không trùng từ — bắt ngữ nghĩa) + lexical làm tie-break nhỏ. (Demo: embed mỗi
      query; prod precompute embedding chunk.)
    """
    uris = scope_frbr_uris or list(session.scalars(sa.select(Document.frbr_uri)))
    qtok = _tokens(query)
    chunks = [ch for uri in uris
              for ch in build_chunks(session, uri, as_of, lang, known_as_of=known_as_of)]

    scored: list[RetrievedChunk] = []
    if embedder is not None and chunks:
        qv = embedder.embed([query])[0]
        cvs = embedder.embed([c.embed_text for c in chunks])
        for ch, cv in zip(chunks, cvs):
            dense = sum(a * b for a, b in zip(qv, cv))          # cosine (đã normalize)
            lex = len(qtok & _tokens(ch.span_text))
            scored.append(RetrievedChunk(
                chunk=ch, score=dense + 0.01 * lex,
                applicable=ch.effect_status in _APPLICABLE))
    else:
        for ch in chunks:
            overlap = qtok & _tokens(ch.span_text)
            if not overlap:
                continue
            scored.append(RetrievedChunk(
                chunk=ch, score=float(len(overlap)),
                applicable=ch.effect_status in _APPLICABLE))

    scored.sort(key=lambda r: (r.applicable, r.score, r.unit_eid), reverse=True)
    return scored[:top_k]


def _row_to_rc(row: ChunkRow, as_of: dt.date, score: float) -> RetrievedChunk:
    applicable = row.valid_to is None or as_of < row.valid_to
    status = EffectStatus.IN_FORCE if applicable else EffectStatus.EXPIRED_CITABLE
    ch = Chunk(unit_eid=row.eid, lang=row.lang, struct_header=row.struct_header,
               span_text=row.span_text, effect_status=status, as_of=as_of)
    return RetrievedChunk(chunk=ch, score=score, applicable=applicable)


def retrieve_indexed(
    session: Session, query: str, as_of: dt.date, *,
    lang: str = "vi", namespaces: tuple[str, ...] = ("kb",), top_k: int = 8,
    embedder=None, rrf_c: int = 60,
) -> list[RetrievedChunk]:
    """L4-backed retrieval — PUSH-DOWN as_of+namespace+lang trong SQL, rồi HYBRID
    BM25 (ts_rank_cd) + dense (pgvector cosine) → RRF. Keep-and-mark: giữ cả expired
    (valid_to≤as_of) nhưng hạ ưu tiên (applicable=False). namespaces = ('kb',) hoặc
    + 'tenant:<id>' — KHÔNG trộn tenant khác."""
    # ① push-down predicate (rẻ, giảm candidate TRƯỚC vector/rank)
    scope = sa.and_(
        ChunkRow.lang == lang, ChunkRow.namespace.in_(namespaces),
        ChunkRow.valid_from <= as_of)
    wide = top_k * 5

    # ② BM25 (FTS 'simple')
    tsq = sa.func.plainto_tsquery("simple", query)
    bm = session.execute(
        sa.select(ChunkRow, sa.func.ts_rank_cd(ChunkRow.tsv, tsq).label("r"))
        .where(scope, ChunkRow.tsv.op("@@")(tsq))
        .order_by(sa.desc("r")).limit(wide)).all()

    # ③ dense (pgvector cosine) — chỉ khi có embedder + embedding đã index
    dense = []
    if embedder is not None:
        qv = embedder.embed([query])[0]
        dense = session.execute(
            sa.select(ChunkRow, ChunkRow.embedding.cosine_distance(qv).label("d"))
            .where(scope, ChunkRow.embedding.is_not(None))
            .order_by(sa.asc("d")).limit(wide)).all()

    # ④ RRF fuse theo id (1/(c+rank) mỗi danh sách)
    rrf: dict[int, float] = {}
    rows: dict[int, ChunkRow] = {}
    for rank, (row, _) in enumerate(bm):
        rrf[row.id] = rrf.get(row.id, 0.0) + 1.0 / (rrf_c + rank)
        rows[row.id] = row
    for rank, (row, _) in enumerate(dense):
        rrf[row.id] = rrf.get(row.id, 0.0) + 1.0 / (rrf_c + rank)
        rows[row.id] = row

    out = [_row_to_rc(rows[i], as_of, s) for i, s in rrf.items()]
    out.sort(key=lambda r: (r.applicable, r.score, r.unit_eid), reverse=True)
    return out[:top_k]
