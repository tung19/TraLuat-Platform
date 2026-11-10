"""W1 — Data pipeline (ingest → cấu trúc hóa + eId → quan hệ → handoff W2)."""

from .structure import ParsedUnit, parse_structure
from .relations import RelationCandidate, extract_relations
from .ingest import (
    build_ingest,
    extract_and_load_relations,
    load_relations_to_w2,
    load_to_w2,
)

__all__ = [
    "ParsedUnit",
    "parse_structure",
    "RelationCandidate",
    "extract_relations",
    "build_ingest",
    "load_to_w2",
    "load_relations_to_w2",
    "extract_and_load_relations",
]
