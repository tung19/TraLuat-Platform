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

from ..w2 import repo
from ..w2.bitemporal import EffectStatus
from ..w2.graph import GraphStore, PostgresGraphStore
from ..w3 import ground
from ..w3.chunker import Chunk
from ..w3.ports import LLMGateway, NLIVerifier
from ..w3.retrieval import RetrievedChunk, retrieve
from .auditor import Auditor, ElementJudge
from .types import Article, AuditEntry, Precedent


def _synth_chunk(art: Article, as_of: dt.date, lang: str = "vi") -> RetrievedChunk:
    """B4: dựng RetrievedChunk từ Article (cho ngữ cảnh adjudicate khi thiếu chunk —
    vd debate resume nạp pool từ checkpoint)."""
    ch = Chunk(unit_eid=art.unit_eid, lang=lang, struct_header=art.unit_eid,
               span_text=art.text or "", effect_status=EffectStatus.IN_FORCE, as_of=as_of)
    return RetrievedChunk(chunk=ch, score=0.0, applicable=True)


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
        elements_by_eid: dict[str, list[str]] | None = None, graph_hops: int = 1,
        graph_store: GraphStore | None = None,
    ) -> None:
        self.s = session
        self.gateway = gateway
        self.nli = nli
        self.element_judge = element_judge
        self.auditor = Auditor(session, element_judge)
        self.elements_by_eid = elements_by_eid or {}
        self.graph_hops = graph_hops   # R_chg: mở rộng ứng viên qua norm-graph (0=tắt)
        self.graph = graph_store or PostgresGraphStore(session)  # ADR-0001: cắm AGE/Neo4j sau

    def _article(self, eid: str, as_of: dt.date, lang: str) -> Article | None:
        text = repo.reconstruct_as_of(self.s, eid, as_of, lang)
        if text is None:
            return None
        return Article(unit_eid=eid, version_date=as_of, text=text,
                       elements=self.elements_by_eid.get(eid, []))

    # — Researcher: thu bằng chứng (uỷ W3 retrieve) + MỞ RỘNG qua norm-graph, KHÔNG verify —
    def _research(self, facts: str, as_of: dt.date, lang: str, top_k: int):
        cands = retrieve(self.s, facts, as_of, lang=lang, top_k=top_k)
        articles, chunk_by_eid = [], {}
        for rc in cands:
            chunk_by_eid[rc.unit_eid] = rc
            articles.append(Article(
                unit_eid=rc.unit_eid, version_date=as_of, text=rc.chunk.span_text,
                elements=self.elements_by_eid.get(rc.unit_eid, []),
            ))
        # ★ R_chg (§4.1, M8-fix): kéo điều DẪN-CHIẾU/HƯỚNG-DẪN qua đồ thị (cites/guides,
        # hiệu-lực-aware) vào ứng viên. Auditor sẽ gác — mở rộng candidate là an toàn.
        if self.graph_hops > 0:
            seen = {a.unit_eid for a in articles}
            for eid in list(seen):
                for reached in self.graph.multihop(eid, ["cites", "guides"],
                                                   max_hops=self.graph_hops, as_of=as_of):
                    if reached in seen:
                        continue
                    art = self._article(reached, as_of, lang)
                    if art is not None:
                        seen.add(reached)
                        articles.append(art)
        return articles, chunk_by_eid

    # — Adjudicator: tổng hợp CHỈ trên verified; rỗng → abstain (H1) —
    def _adjudicate(self, party, facts, as_of, verified, chunk_by_eid, lang, tenant_id):
        if not verified:
            return PartyResult(party, abstain=True, reason="insufficient_basis")
        # B4: eid thiếu chunk (vd resume từ checkpoint) → dựng chunk từ Article,
        # không để rơi khỏi ngữ cảnh LLM.
        ctx = [chunk_by_eid.get(a.unit_eid) or _synth_chunk(a, as_of, lang) for a in verified]
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
        case_id: str = "case",
    ) -> Adjudication:
        if mode == "multi_role":
            from .multi_role import MultiRoleReasoner
            mr = MultiRoleReasoner(
                self.s, gateway=self.gateway, nli=self.nli,
                element_judge=self.element_judge, elements_by_eid=self.elements_by_eid,
                top_k=top_k)
            return mr.run(case, as_of, tenant_id=tenant_id, case_id=case_id, lang=lang).adjudication

        from .precedent_store import match_by_eids

        parties = case.parties or ["(chung)"]
        results, all_verified, all_prec, trail = [], [], [], []
        seen_prec: set[str] = set()
        for party in parties:
            facts = case.facts_by_party.get(party, case.facts)
            articles, chunk_by_eid = self._research(facts, as_of, lang, top_k)
            # Researcher: án lệ tựa vào điều ứng viên (Auditor sẽ prune theo verified)
            cand_prec = match_by_eids(self.s, [a.unit_eid for a in articles])
            audit = self.auditor.audit(facts, as_of, articles, cand_prec, lang=lang)
            trail.extend(audit.trail)
            all_verified.extend(audit.verified_articles)
            for p in audit.verified_precedents:        # dedupe xuyên bên
                if p.precedent_id not in seen_prec:
                    seen_prec.add(p.precedent_id)
                    all_prec.append(p)
            results.append(self._adjudicate(
                party, facts, as_of, audit.verified_articles, chunk_by_eid, lang, tenant_id))

        draft = "\n\n".join(f"[{r.party}] {r.relief}" for r in results if r.relief)
        return Adjudication(
            parties=results, verified_articles=all_verified, verified_precedents=all_prec,
            audit_trail=trail, draft=draft, ai_label=True,
        )
