"""W1 — Data pipeline (ingest → cấu trúc hóa + eId → quan hệ → handoff W2)."""

from .ingest import (
    build_ingest,
    derive_frbr_uri,
    extract_and_load_relations,
    ingest_document,
    load_relations_to_w2,
    load_to_w2,
)
from .metadata import DocMeta, extract_effective_overrides, extract_metadata
from .ocr import NoOCR, OCREngine, PassthroughOCR
from .ocr_detect import FullPageOCR, GridLineDetector, LineDetector, PaddleLineDetector
from .relations import RelationCandidate, extract_relations
from .source import (
    DocumentSource,
    IngestOutcome,
    InMemorySource,
    JsonlFileSource,
    RawDocument,
    ingest_source,
)
from .structure import ParsedUnit, parse_structure

__all__ = [
    "DocMeta",
    "DocumentSource",
    "FullPageOCR",
    "GridLineDetector",
    "InMemorySource",
    "IngestOutcome",
    "JsonlFileSource",
    "LineDetector",
    "NoOCR",
    "OCREngine",
    "PaddleLineDetector",
    "ParsedUnit",
    "PassthroughOCR",
    "RawDocument",
    "RelationCandidate",
    "build_ingest",
    "derive_frbr_uri",
    "extract_and_load_relations",
    "extract_effective_overrides",
    "extract_metadata",
    "extract_relations",
    "ingest_document",
    "ingest_source",
    "load_relations_to_w2",
    "load_to_w2",
    "parse_structure",
]
