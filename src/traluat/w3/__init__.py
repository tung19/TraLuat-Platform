"""W3 — Retrieval + Grounding + LLM orchestration.

Lõi TẤT ĐỊNH (chunker giữ-span · retrieve keep-and-mark · gates gate1/2/3b · R1
abstain) chạy KHÔNG cần model. Các port cắm-được (LLMGateway/NLI/Embedder/Reranker)
có stub để chạy ngay (EchoLLMGateway/HoldNLI/HashEmbedder) và impl thật cắm sau
(ClaudeLLMGateway). Orchestrator ráp cả vòng: retrieve→generate→verify→abstain/answer.

Defer (cắm là chạy): bge-m3 dense + BM25 + RRF + rerank · gate3 NLI thật · L-MARS
6-lớp + Faith-Search · eval harness char-level + gold. Spec: docs/specs/w3-*.md.
"""

from .as_of import AsOfPlan, resolve_as_of
from .chunker import Chunk, build_chunks
from .conflict_detect import (
    ConflictCandidate,
    ConflictFinding,
    DeonticConflictDetector,
    NoSemantic,
    SemanticConflictDetector,
    deontic_polarity,
    detect_conflicts,
    find_and_resolve_conflicts,
)
from .gateway import (
    BaseLLMGateway,
    ClaudeLLMGateway,
    EchoLLMGateway,
    NotConfigured,
    TenantLeak,
    wrap_untrusted,
)
from .grounding import GateResult, GroundingResult, ground, verify_citation
from .indexer import reindex_document
from .orchestrator import Answer, answer_question, answer_with_resolution
from .ports import (
    Citation,
    Embedder,
    LLMGateway,
    LLMResult,
    NLIVerifier,
    Reranker,
)
from .retrieval import RetrievedChunk, retrieve, retrieve_indexed
from .stubs import HashEmbedder, HoldNLI, KeywordNLIVerifier, NoopReranker

__all__ = [
    "Answer",
    "AsOfPlan",
    "BaseLLMGateway",
    "Chunk",
    "Citation",
    "ClaudeLLMGateway",
    "ConflictCandidate",
    "ConflictFinding",
    "DeonticConflictDetector",
    "EchoLLMGateway",
    "Embedder",
    "GateResult",
    "GroundingResult",
    "HashEmbedder",
    "HoldNLI",
    "KeywordNLIVerifier",
    "LLMGateway",
    "LLMResult",
    "NLIVerifier",
    "NoSemantic",
    "NoopReranker",
    "NotConfigured",
    "Reranker",
    "RetrievedChunk",
    "SemanticConflictDetector",
    "TenantLeak",
    "answer_question",
    "answer_with_resolution",
    "build_chunks",
    "deontic_polarity",
    "detect_conflicts",
    "find_and_resolve_conflicts",
    "ground",
    "reindex_document",
    "resolve_as_of",
    "retrieve",
    "retrieve_indexed",
    "verify_citation",
    "wrap_untrusted",
]
