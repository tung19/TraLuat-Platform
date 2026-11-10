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
from ..w2.models import Document
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
