"""W3 — Retrieval + Grounding + LLM orchestration.

Lõi TẤT ĐỊNH (chunker giữ-span · retrieve keep-and-mark · gates gate1/2/3b · R1
abstain) chạy KHÔNG cần model. Các port cắm-được (LLMGateway/NLI/Embedder/Reranker)
có stub để chạy ngay (EchoLLMGateway/HoldNLI/HashEmbedder) và impl thật cắm sau
(ClaudeLLMGateway). Orchestrator ráp cả vòng: retrieve→generate→verify→abstain/answer.

Defer (cắm là chạy): bge-m3 dense + BM25 + RRF + rerank · gate3 NLI thật · L-MARS
6-lớp + Faith-Search · eval harness char-level + gold. Spec: docs/specs/w3-*.md.
"""

from .chunker import Chunk, build_chunks
from .retrieval import RetrievedChunk, retrieve
from .grounding import GateResult, GroundingResult, ground, verify_citation
from .ports import (
    Citation, Embedder, LLMGateway, LLMResult, NLIVerifier, Reranker,
)
from .gateway import (
    BaseLLMGateway, ClaudeLLMGateway, EchoLLMGateway, NotConfigured, TenantLeak,
    wrap_untrusted,
)
from .stubs import HashEmbedder, HoldNLI, NoopReranker
from .orchestrator import Answer, answer_question

__all__ = [
    "Chunk", "build_chunks",
    "RetrievedChunk", "retrieve",
    "GateResult", "GroundingResult", "ground", "verify_citation",
    "Citation", "Embedder", "LLMGateway", "LLMResult", "NLIVerifier", "Reranker",
    "BaseLLMGateway", "ClaudeLLMGateway", "EchoLLMGateway", "NotConfigured",
    "TenantLeak", "wrap_untrusted",
    "HashEmbedder", "HoldNLI", "NoopReranker",
    "Answer", "answer_question",
]
