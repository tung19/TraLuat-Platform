"""W3 — Retrieval + Grounding (slice-1: xương sống trích dẫn TẤT ĐỊNH).

Slice-1 cố tình KHÔNG dùng model: chunker giữ-span + retrieval keep-and-mark
effect_status + citation gates tất định (gate1 tồn tại · gate2 hiệu-lực@anchor ·
gate3b exactness số/ngày) + abstain-khi-rỗng. Defer (cần model/gold):
bge-m3 dense + BM25 tiếng Việt + RRF/rerank · gate3 NLI · LLMGateway · Faith-
Search 6-lớp · eval harness char-level. Spec: docs/specs/w3-ai-retrieval-grounding.md.
"""

from .chunker import Chunk, build_chunks
from .retrieval import RetrievedChunk, retrieve
from .grounding import GateResult, GroundingResult, ground, verify_citation

__all__ = [
    "Chunk", "build_chunks",
    "RetrievedChunk", "retrieve",
    "GateResult", "GroundingResult", "ground", "verify_citation",
]
