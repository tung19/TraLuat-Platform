"""Kiểu dữ liệu W4 — hợp đồng thu hẹp (narrowing): mỗi tầng chỉ CO NHỎ tập."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class Article:
    unit_eid: str                                   # khoá canonical W2
    version_date: dt.date | None = None             # version đang xét (H3 version-match)
    text: str | None = None                         # nguyên văn tại as_of (so khớp H3)
    elements: list[str] = field(default_factory=list)       # yếu tố cấu thành (checklist)
    interpretations: list[str] = field(default_factory=list)  # án lệ/NQ/TT hướng dẫn
    flags: list[str] = field(default_factory=list)          # vd 'transitional'


@dataclass
class Precedent:
    precedent_id: str
    cited_unit_eids: list[str] = field(default_factory=list)
    situation: str = ""
    solution: str = ""


@dataclass
class AuditEntry:
    unit_eid: str
    accepted: bool
    gate: int | None = None        # cổng quyết định (1|2|3); None nếu accepted
    reason: str = ""               # citation_unreachable|version_mismatch|temporally_invalid|not_applicable
    detail: str = ""               # vd yếu tố nào unsatisfied / needs_review
    flags: list[str] = field(default_factory=list)


@dataclass
class AuditResult:
    verified_articles: list[Article] = field(default_factory=list)
    verified_precedents: list[Precedent] = field(default_factory=list)
    trail: list[AuditEntry] = field(default_factory=list)   # MỌI điều + lý do loại (giải trình)
