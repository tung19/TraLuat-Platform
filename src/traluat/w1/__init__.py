"""W1 — Data pipeline (ingest → cấu trúc hóa + eId → quan hệ → handoff W2)."""

from .structure import ParsedUnit, parse_structure
from .metadata import DocMeta, extract_effective_overrides, extract_metadata
from .relations import RelationCandidate, extract_relations
from .ingest import (
    build_ingest,
    derive_frbr_uri,
    extract_and_load_relations,
    ingest_document,
    load_relations_to_w2,
    load_to_w2,
)
from .source import (
    DocumentSource,
    InMemorySource,
    IngestOutcome,
    JsonlFileSource,
    RawDocument,
    ingest_source,
)
from .ocr import NoOCR, OCREngine, PassthroughOCR

__all__ = [
    "ParsedUnit",
    "parse_structure",
    "DocMeta",
    "extract_metadata",
    "extract_effective_overrides",
    "RelationCandidate",
    "extract_relations",
    "build_ingest",
    "derive_frbr_uri",
    "ingest_document",
    "load_to_w2",
    "load_relations_to_w2",
    "extract_and_load_relations",
    "DocumentSource",
    "InMemorySource",
    "JsonlFileSource",
    "RawDocument",
    "IngestOutcome",
    "ingest_source",
    "OCREngine",
    "NoOCR",
    "PassthroughOCR",
]
