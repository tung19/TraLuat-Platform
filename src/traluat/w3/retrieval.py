"""RetrievalService (L5) — slice-1: lexical keep-and-MARK, hiệu-lực-aware.

★ keep-and-MARK (§1 / principle #4): KHÔNG drop cứng theo hiệu lực. Mỗi ứng viên
mang effect_status@as_of; EXPIRED_CITABLE/TRANSITIONAL vẫn trả (kèm nhãn), chỉ
HẠ ưu tiên khỏi 'thắng'; NOT_YET đánh dấu 'chưa hiệu lực'.

`retrieve` giữ đường lexical/demo cho core tests; runtime dùng IndexedRetriever:
FTS + dense bge-m3 (1024d) + RRF. BM25 tiếng Việt/cross-encoder chưa cấu hình.
"""

from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..w2 import repo
from ..w2.bitemporal import EffectStatus
from ..w2.models import Chunk as ChunkRow
from ..w2.models import Document, Unit
from .chunker import Chunk, build_chunks
from .indexer import embedding_identity, validate_vectors

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
    scope_frbr_uris: list[str] | None = None,
    known_as_of: dt.datetime | None = None,
) -> list[RetrievedChunk]:
    """L4-backed retrieval — PUSH-DOWN as_of+namespace+lang trong SQL, rồi HYBRID
    FTS (ts_rank_cd) + dense (pgvector cosine) → RRF. Keep-and-mark: giữ cả expired
    (valid_to≤as_of) nhưng hạ ưu tiên (applicable=False). namespaces = ('kb',) hoặc
    + 'tenant:<id>' — KHÔNG trộn tenant khác."""
    # ① push-down predicate (rẻ, giảm candidate TRƯỚC vector/rank)
    if not 1 <= top_k <= 100:
        raise ValueError("top_k must be between 1 and 100")
    known = known_as_of or repo._db_now(session)
    scope = sa.and_(
        ChunkRow.lang == lang, ChunkRow.namespace.in_(namespaces),
        ChunkRow.valid_from <= as_of)
    if scope_frbr_uris is not None:
        scope = sa.and_(scope, ChunkRow.unit_id.in_(
            sa.select(Unit.id).join(Document).where(Document.frbr_uri.in_(scope_frbr_uris))))
    wide = top_k * 5

    # ② PostgreSQL FTS 'simple' (not BM25)
    tsq = sa.func.plainto_tsquery("simple", query)
    bm = session.execute(
        sa.select(ChunkRow, sa.func.ts_rank_cd(ChunkRow.tsv, tsq).label("r"))
        .where(scope, ChunkRow.tsv.op("@@")(tsq))
        .order_by(sa.desc("r")).limit(wide)).all()

    # ③ dense (pgvector cosine) — chỉ khi có embedder + embedding đã index
    dense = []
    if embedder is not None:
        vectors = embedder.embed([query])
        validate_vectors(vectors, 1)
        qv = vectors[0]
        dense = session.execute(
            sa.select(ChunkRow, ChunkRow.embedding.cosine_distance(qv).label("d"))
            .where(scope, ChunkRow.embedding.is_not(None),
                   ChunkRow.embedding_model == embedding_identity(embedder))
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

    out, seen = [], set()
    for i, score in rrf.items():
        row = rows[i]
        text, status = repo.citable_text(session, row.eid, as_of, lang, known_as_of=known)
        # Indexes are derived. A stale amendment must never become model context.
        if text != row.span_text or row.eid in seen:
            continue
        seen.add(row.eid)
        rc = _row_to_rc(row, as_of, score)
        rc.chunk.frbr_uri = session.scalar(sa.select(Document.frbr_uri).join(Unit).where(
            Unit.id == row.unit_id))
        rc.chunk.effect_status = status
        rc.applicable = status in _APPLICABLE
        out.append(rc)
    out.sort(key=lambda r: (r.applicable, r.score, r.unit_eid), reverse=True)
    return out[:top_k]


class IndexedRetriever:
    """Reusable runtime adapter; query-only embeddings, canonical evidence validation."""

    def __init__(self, embedder=None, reranker=None):
        self.embedder = embedder
        self.reranker = reranker

    def __call__(self, session, query, as_of, *, top_k=8, **kwargs):
        candidates = retrieve_indexed(session, query, as_of, embedder=self.embedder,
                                      top_k=min(top_k * 3, 100) if self.reranker else top_k,
                                      **kwargs)
        if self.reranker and candidates:
            scores = self.reranker.rerank(query, [c.chunk.embed_text for c in candidates])
            if len(scores) != len(candidates) or not all(math.isfinite(x) for x in scores):
                raise ValueError("reranker returned invalid scores")
            for candidate, score in zip(candidates, scores):
                candidate.score = score
            candidates.sort(key=lambda c: (c.applicable, c.score), reverse=True)
        return candidates[:top_k]
