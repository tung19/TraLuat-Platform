"""GroundingService (L6) — slice-1: Citation Verifier cổng TẤT ĐỊNH + abstain.

Cổng (spec §2), slice-1 chỉ cổng KHÔNG cần model:
  gate1 — unit_eid CÓ THẬT trong KB.                                (RULE)
  gate2 — effect_status(eid, anchor) ∈ {IN_FORCE, TRANSITIONAL} và có bản text
          tại anchor (H3: trích đúng version-tại-ngày, không version cũ).   (RULE)
  gate3b — EXACTNESS: mọi đại lượng số/ngày trong claim phải XUẤT HIỆN trong
          nguồn ('15 ngày' ≠ '30 ngày' → chặn paraphrase-sai-số, F9/X2).    (RULE)
Defer: gate3 NLI 'hỗ trợ pháp lý' (ML, PROMOTE/HOLD) + L-MARS 6-lớp + Faith-Search.

Sufficiency floor (R1): draft RỖNG citation → ABSTAIN (không bịa). Không có
citation nào qua đủ cổng → ABSTAIN. Nguyên tắc #6: mơ hồ thì abstain, không auto.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

import sqlalchemy as sa

from ..w2 import repo
from ..w2.bitemporal import EffectStatus
from ..w2.models import Unit
from .ports import NLIVerifier

_APPLICABLE = {EffectStatus.IN_FORCE, EffectStatus.TRANSITIONAL_APPLIES}

# đại lượng pháp lý: số + đơn vị (tránh bắt 'Điều 3' làm đại lượng) + ngày dd/mm/yyyy
_RE_QUANTITY = re.compile(
    r"(\d[\d.]*)\s*(ngày|tháng|năm|tuần|giờ|tỷ|triệu|nghìn|đồng|%|phần trăm|lần)",
    re.IGNORECASE,
)
_RE_DATE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")


def _facts(text: str) -> set[str]:
    """Trích tập đại lượng chuẩn hoá từ text ('15 ngày', '20 tỷ', '01/06/2023')."""
    t = unicodedata.normalize("NFC", text).lower()
    facts = {f"{num.replace('.', '')} {unit.lower()}" for num, unit in _RE_QUANTITY.findall(t)}
    facts |= {f"{int(d):02d}/{int(m):02d}/{y}" for d, m, y in _RE_DATE.findall(t)}
    return facts


@dataclass
class GateResult:
    unit_eid: str
    gate1_exists: bool
    gate2_effective: bool
    gate3b_exact: bool
    status: EffectStatus
    source_text: str | None
    missing_facts: set[str] = field(default_factory=set)
    gate3_nli: str | None = None       # 'promote'|'hold'|None (defer; HOLD KHÔNG veto)

    @property
    def passed(self) -> bool:
        # gate3 (NLI) chỉ PROMOTE/HOLD — KHÔNG veto → không nằm trong điều kiện pass.
        return self.gate1_exists and self.gate2_effective and self.gate3b_exact


def verify_citation(
    session: Session, claim: str, unit_eid: str, anchor: dt.date, lang: str = "vi",
    nli: NLIVerifier | None = None,
) -> GateResult:
    """Verify 1 trích dẫn qua 3 cổng tất định (+ gate3 NLI tuỳ chọn, không veto)."""
    exists = session.scalar(sa.select(Unit.id).where(Unit.eid == unit_eid)) is not None
    if not exists:
        return GateResult(unit_eid, False, False, False, EffectStatus.ABSENT, None)

    text, status = repo.citable_text(session, unit_eid, anchor, lang)
    gate2 = status in _APPLICABLE and text is not None

    missing = _facts(claim) - _facts(text or "")
    gate3b = not missing  # mọi số/ngày trong claim có trong nguồn
    nli_verdict = nli.supports(claim, text) if (nli and text) else None
    return GateResult(unit_eid, True, gate2, gate3b, status, text, missing, nli_verdict)


@dataclass
class GroundingResult:
    abstain: bool
    reason: str                       # "" nếu không abstain
    gates: list[GateResult] = field(default_factory=list)
    supported_eids: list[str] = field(default_factory=list)


def ground(
    session: Session, claim: str, anchor: dt.date, citations: list[str], lang: str = "vi",
    nli: NLIVerifier | None = None,
) -> GroundingResult:
    """Kiểm 1 khẳng định + danh sách trích dẫn → giữ hay ABSTAIN.

    R1 sufficiency floor: rỗng citation → abstain. Không citation nào qua đủ 3
    cổng → abstain (không trả câu không neo được nguồn áp dụng được).
    """
    if not citations:
        return GroundingResult(True, "insufficient_retrieval")

    gates = [verify_citation(session, claim, eid, anchor, lang, nli) for eid in citations]
    supported = [g.unit_eid for g in gates if g.passed]
    if not supported:
        return GroundingResult(True, "no_supported_citation", gates=gates)
    return GroundingResult(False, "", gates=gates, supported_eids=supported)
