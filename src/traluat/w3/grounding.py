"""Ground every statement: existence, temporal validity, quantity, evidence.

Exact complete-source statements work without a semantic model. Paraphrases
require a mapped complete source quote and a non-demo verifier's PROMOTE;
HOLD or missing evidence means abstention. This is a support gate, not a claim
of legally calibrated confidence or a substitute for human review.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..w2 import repo
from ..w2.bitemporal import EffectStatus
from ..w2.models import Unit
from .ports import Citation, NLIVerifier

_APPLICABLE = {EffectStatus.IN_FORCE, EffectStatus.TRANSITIONAL_APPLIES}

# đại lượng pháp lý: số + đơn vị (tránh bắt 'Điều 3' làm đại lượng) + ngày dd/mm/yyyy
_RE_QUANTITY = re.compile(
    r"(?<![\w.,+\-])([+-]?\d+(?:[.,]\d+)*)"
    r"(?:\s*(?:[-–—]|đến|tới)\s*([+-]?\d+(?:[.,]\d+)*))?\s*"
    r"(phần trăm|ngày|tháng|năm|tuần|giờ|tỷ|triệu|nghìn|đồng|%|lần)(?!\w)",
    re.IGNORECASE,
)
_RE_DATE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")


def _number(value: str, lang: str) -> str:
    if lang == "vi":
        # Vietnamese: '.' groups thousands and ',' denotes the decimal part.
        if "," in value:
            value = value.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+", value):
            value = value.replace(".", "")
    elif "," in value:
        value = value.replace(",", "")
    try:
        return format(Decimal(value).normalize(), "f")
    except InvalidOperation:
        return value  # malformed/ambiguous numbers never silently lose digits


def _facts(text: str, lang: str = "vi") -> set[str]:
    """Trích tập đại lượng chuẩn hoá từ text ('15 ngày', '20 tỷ', '01/06/2023')."""
    t = unicodedata.normalize("NFC", text).lower().replace("−", "-")
    facts = {
        f"{('range:' + _number(num, lang) + ':' + _number(end, lang)) if end else _number(num, lang)} {unit.lower()}"
        for num, end, unit in _RE_QUANTITY.findall(t)
    }
    facts |= {f"{int(d):02d}/{int(m):02d}/{y}" for d, m, y in _RE_DATE.findall(t)}
    return facts


def _normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split()).strip()


def claims(text: str) -> list[str]:
    """Conservative sentence/list boundaries, preserving decimal punctuation."""
    return [p.strip() for p in re.split(r"(?<=[.!?;])\s+|\n+", text) if p.strip()]


def _extractive(claim: str, source: str) -> bool:
    # Match complete source statements, never a substring that drops a negation
    # or condition (e.g. 'được' extracted from 'không được').
    return _normal(claim) in {_normal(s) for s in claims(source)}


@dataclass
class GateResult:
    unit_eid: str
    gate1_exists: bool
    gate2_effective: bool
    gate3b_exact: bool
    status: EffectStatus
    source_text: str | None
    missing_facts: set[str] = field(default_factory=set)
    gate3_nli: str | None = None       # HOLD cannot support a paraphrase
    claim: str = ""
    semantic_supported: bool = False

    @property
    def passed(self) -> bool:
        return (self.gate1_exists and self.gate2_effective
                and self.gate3b_exact and self.semantic_supported)


def verify_citation(
    session: Session, claim: str, unit_eid: str, anchor: dt.date, lang: str = "vi",
    nli: NLIVerifier | None = None, known_as_of: dt.datetime | None = None,
    evidence: Citation | None = None,
) -> GateResult:
    """Verify one statement against one citation and optional quote mapping."""
    exists = session.scalar(sa.select(Unit.id).where(Unit.eid == unit_eid)) is not None
    if not exists:
        return GateResult(unit_eid, False, False, False, EffectStatus.ABSENT, None)

    text, status = repo.citable_text(session, unit_eid, anchor, lang, known_as_of=known_as_of)
    gate2 = status in _APPLICABLE and text is not None

    missing = _facts(claim, lang) - _facts(text or "", lang)
    gate3b = not missing  # mọi số/ngày trong claim có trong nguồn
    nli_verdict = nli.supports(claim, text) if (nli and text) else None
    exact = bool(text) and _extractive(claim, text)
    # A verifier's PROMOTE alone is insufficient: a paraphrase must identify its
    # exact claim and quote a complete source statement. HOLD requires review.
    quoted = bool(text and evidence and evidence.claim and evidence.quote
                  and _normal(evidence.quote)
                  and _normal(evidence.claim) == _normal(claim)
                  and _normal(evidence.quote) in _normal(text)
                  and all(_extractive(q, text) for q in claims(evidence.quote))
                  and _facts(claim, lang) <= _facts(evidence.quote, lang))
    verifier_usable = nli is not None and not getattr(nli, "demo_only", False)
    supported = exact or (quoted and verifier_usable and nli_verdict == "promote")
    return GateResult(unit_eid, True, gate2, gate3b, status, text, missing,
                      nli_verdict, claim, supported)


@dataclass
class GroundingResult:
    abstain: bool
    reason: str                       # "" nếu không abstain
    gates: list[GateResult] = field(default_factory=list)
    supported_eids: list[str] = field(default_factory=list)


def ground(
    session: Session, claim: str, anchor: dt.date, citations: list[str | Citation], lang: str = "vi",
    nli: NLIVerifier | None = None, known_as_of: dt.datetime | None = None,
) -> GroundingResult:
    """Every statement must have at least one valid supporting citation."""
    parts = claims(claim)
    if not citations or not parts:
        return GroundingResult(True, "insufficient_retrieval")
    gates: list[GateResult] = []
    supported: list[str] = []
    for part in parts:
        part_gates = []
        for cite in citations:
            eid = cite if isinstance(cite, str) else cite.unit_eid
            evidence = None if isinstance(cite, str) else cite
            # Cross-date legal applicability is never inferred from a model's
            # chosen anchor. Multi-anchor legal questions require human review.
            if evidence and evidence.anchor not in (None, anchor):
                continue
            part_gates.append(verify_citation(
                session, part, eid, anchor, lang, nli, known_as_of, evidence))
        gates.extend(part_gates)
        passed = [g.unit_eid for g in part_gates if g.passed]
        if not passed:
            return GroundingResult(True, "no_supported_citation", gates=gates)
        supported.extend(passed)
    return GroundingResult(False, "", gates=gates,
                           supported_eids=list(dict.fromkeys(supported)))
