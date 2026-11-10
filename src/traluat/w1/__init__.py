"""W1 — Data pipeline (ingest → cấu trúc hóa + eId → quan hệ → handoff W2)."""

from .structure import ParsedUnit, parse_structure
from .ingest import build_ingest, load_to_w2

__all__ = ["ParsedUnit", "parse_structure", "build_ingest", "load_to_w2"]
