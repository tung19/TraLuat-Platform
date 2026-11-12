"""Ports (Protocol) cho các thành phần CẮM-ĐƯỢC của W3 — thay stub↔thật không đụng lõi.

Lõi grounding/retrieval TẤT ĐỊNH không phụ thuộc các port này; chúng chỉ thêm
sức mạnh (dense/rerank/NLI/LLM). Mỗi port có ít nhất 1 stub (stubs.py) để pipeline
chạy ngay, và 1 impl thật cắm sau (gateway.ClaudeLLMGateway, embed bge-m3…).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable


# ── LLM ─────────────────────────────────────────────────────────────────────
@dataclass
class Citation:
    unit_eid: str
    anchor: dt.date | None = None   # None → orchestrator dùng as_of câu hỏi
    claim: str | None = None        # một khẳng định trong draft (paraphrase)
    quote: str | None = None        # nguyên văn hỗ trợ; phải khớp nguồn tại anchor


@dataclass
class LLMResult:
    text: str
    citations: list[Citation] = field(default_factory=list)
    ai_label: bool = True           # Luật 71/2025: output AI phải gắn nhãn
    model: str | None = None
    provenance_ok: bool = True
    raw: object | None = None


@runtime_checkable
class LLMGateway(Protocol):
    def generate(
        self, query: str, context_chunks: list, *,
        as_of: dt.date, node: str = "answer",
        tenant_id: str | None = None, lang: str = "vi",
    ) -> LLMResult: ...


# ── NLI (PROMOTE needs evidence; HOLD cannot support paraphrases) ──────────
NLIVerdict = Literal["promote", "hold"]


@runtime_checkable
class NLIVerifier(Protocol):
    def supports(self, claim: str, source: str) -> NLIVerdict: ...


# ── Embedding / Rerank (dense hybrid — defer bge-m3/cross-encoder thật) ──────
@runtime_checkable
class Embedder(Protocol):
    dim: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[str]) -> list[float]: ...
