"""Orchestrator một-lượt (§4,§6) — Researcher → Auditor → Adjudicator, per-party.

Hợp đồng THU HẸP: mỗi tầng chỉ co nhỏ tập. Adjudicator CHỈ đọc verified_* (không
với tay qua cổng). verified-set rỗng → ABSTAIN insufficient_basis (H1 — KHÔNG bịa
phán quyết từ party_facts trần). Mọi LLM qua gateway (W3); cổng hậu-draft = W3.ground.

Slice-1: mode='single'. Precedent store chưa có → verified_precedents=[]. `elements`
đóng băng offline, nạp qua elements_by_eid (chưa có → điều không checklist = áp dụng).
Defer: Reasoner đa vai (mode='multi_role'), Researcher multihop cause-of-action,
affirmative-defense (H2), schema cứu trợ dân sự chi tiết.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from ..w2.bitemporal import EffectStatus
from ..w3 import ground
from ..w3.ports import LLMGateway, NLIVerifier
from ..w3.retrieval import retrieve
from .auditor import Auditor, ElementJudge
from .types import Article, AuditEntry, Precedent


@dataclass
class CaseInput:
    facts: str                                      # tình tiết chung
    parties: list[str] = field(default_factory=list)          # tên bên/yêu cầu
    facts_by_party: dict[str, str] = field(default_factory=dict)  # tình tiết riêng từng bên


@dataclass
class PartyResult:
    party: str
    abstain: bool
    reason: str = ""                                # insufficient_basis | no_supported_citation | ""
    relief: str = ""                                # văn bản kết luận (có trích dẫn inline)
    citations: list[str] = field(default_factory=list)
    effect_status: dict[str, EffectStatus] = field(default_factory=dict)


@dataclass
class Adjudication:
    parties: list[PartyResult]
    verified_articles: list[Article] = field(default_factory=list)
    verified_precedents: list[Precedent] = field(default_factory=list)
    audit_trail: list[AuditEntry] = field(default_factory=list)
    draft: str = ""
    ai_label: bool = True


class ReasoningEngine:
    """Tầng ĐIỀU PHỐI — không tự retrieval/NLI cấp claim (uỷ cho W3)."""

    def __init__(
        self, session: Session, *, gateway: LLMGateway,
        nli: NLIVerifier | None = None, element_judge: ElementJudge | None = None,
        elements_by_eid: dict[str, list[str]] | None = None,
    ) -> None:
        self.s = session
        self.gateway = gateway
        self.nli = nli
        self.auditor = Auditor(session, element_judge)
        self.elements_by_eid = elements_by_eid or {}

    # — Researcher: thu bằng chứng (uỷ W3 retrieve), KHÔNG verify —
    def _research(self, facts: str, as_of: dt.date, lang: str, top_k: int):
        cands = retrieve(self.s, facts, as_of, lang=lang, top_k=top_k)
        articles, chunk_by_eid = [], {}
        for rc in cands:
            chunk_by_eid[rc.unit_eid] = rc
            articles.append(Article(
                unit_eid=rc.unit_eid, version_date=as_of, text=rc.chunk.span_text,
                elements=self.elements_by_eid.get(rc.unit_eid, []),
            ))
        return articles, chunk_by_eid

    # — Adjudicator: tổng hợp CHỈ trên verified; rỗng → abstain (H1) —
    def _adjudicate(self, party, facts, as_of, verified, chunk_by_eid, lang, tenant_id):
        if not verified:
            return PartyResult(party, abstain=True, reason="insufficient_basis")
        ctx = [chunk_by_eid[a.unit_eid] for a in verified if a.unit_eid in chunk_by_eid]
        draft = self.gateway.generate(facts, ctx, as_of=as_of, node="adjudicator",
                                      tenant_id=tenant_id, lang=lang)
        # ★ Adjudicator CHỈ được trích trong tập verified (hợp đồng thu hẹp §2) —
        # loại trích dẫn ngoài verified (kiến thức tham số / điều đã bị loại ở cổng).
        allowed = {a.unit_eid for a in verified}
        cited = [c.unit_eid for c in draft.citations if c.unit_eid in allowed]
        g = ground(self.s, draft.text, as_of, cited, lang, self.nli)
        if g.abstain:
            return PartyResult(party, abstain=True, reason=g.reason, relief=draft.text)
        return PartyResult(
            party, abstain=False, relief=draft.text, citations=g.supported_eids,
            effect_status={gt.unit_eid: gt.status for gt in g.gates if gt.passed},
        )

    def analyze(
        self, case: CaseInput, as_of: dt.date, *,
        mode: Literal["single", "multi_role"] = "single",
        tenant_id: str | None = None, lang: str = "vi", top_k: int = 8,
    ) -> Adjudication:
        if mode == "multi_role":
            raise NotImplementedError("Reasoner đa vai = Phase 4 (§5) — chưa build")

        parties = case.parties or ["(chung)"]
        results, all_verified, trail = [], [], []
        for party in parties:
            facts = case.facts_by_party.get(party, case.facts)
            articles, chunk_by_eid = self._research(facts, as_of, lang, top_k)
            audit = self.auditor.audit(facts, as_of, articles, lang=lang)
            trail.extend(audit.trail)
            all_verified.extend(audit.verified_articles)
            results.append(self._adjudicate(
                party, facts, as_of, audit.verified_articles, chunk_by_eid, lang, tenant_id))

        draft = "\n\n".join(f"[{r.party}] {r.relief}" for r in results if r.relief)
        return Adjudication(
            parties=results, verified_articles=all_verified, verified_precedents=[],
            audit_trail=trail, draft=draft, ai_label=True,
        )
