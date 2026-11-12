"""LegalService (L7 serving) — vỏ tenancy + residency + audit quanh ReasoningEngine.

Bất biến W5: (1) không request nào vào engine mà thiếu tenant_id (TenantContext ép);
(2) không câu trả lời nào rời service mà thiếu nhãn AI + trace_id; (3) dữ liệu khách
không ra Claude (EgressPolicy); (4) mọi quyết định route được audit write-ahead.

Engine không đụng — W5 chỉ cung cấp xương sống + cô lập + serving. FastAPI/Celery
(infra lift PAKTON) cắm trên service này sau; không ảnh hưởng bất biến.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..w3 import Answer, answer_question
from ..w3.local_gateway import LocalModelError
from ..w3.ports import LLMGateway, NLIVerifier
from ..w4 import Adjudication, CaseInput, ReasoningEngine
from ..w4.auditor import ElementJudge
from .audit import AuditLog
from .egress import PUBLIC_KB, EgressPolicy, LLMDestination, RouteDecision
from .tenancy import TenantContext
from .tracing import span


@dataclass
class ServiceResponse:
    answered: bool
    trace_id: str
    route: RouteDecision
    ai_label: bool = True                 # Luật 71/2025 — luôn gắn
    adjudication: Adjudication | None = None
    answer: Answer | None = None          # cho lookup() (câu hỏi thuần KB)
    reason: str = ""                      # "" nếu answered


class LegalService:
    def __init__(
        self, session: Session, *,
        local_gateway: LLMGateway,
        claude_gateway: LLMGateway | None = None,
        nli: NLIVerifier | None = None,
        element_judge: ElementJudge | None = None,
        elements_by_eid: dict[str, list[str]] | None = None,
        egress: EgressPolicy | None = None,
        audit: AuditLog | None = None,
        metrics=None,
        knowledge_session_factory=None,
        retriever=None,
    ) -> None:
        self.s = session
        self.local_gateway = local_gateway
        self.claude_gateway = claude_gateway
        self.nli = nli
        self.element_judge = element_judge
        self.elements_by_eid = elements_by_eid
        self.egress = egress or EgressPolicy()
        self.audit = audit or AuditLog()
        self.metrics = metrics
        self.knowledge_session_factory = knowledge_session_factory
        self.retriever = retriever

    def _gateway_for(self, dest: LLMDestination) -> LLMGateway | None:
        if dest == LLMDestination.LOCAL:
            return self.local_gateway
        if dest == LLMDestination.CLAUDE:
            return self.claude_gateway
        return None

    def _local_healthy(self) -> bool:
        fn = getattr(self.local_gateway, "healthy", None)
        return bool(fn()) if callable(fn) else True

    def _route(self, ctx, provenances, action, local_available, trace_id, actor):
        """Chung: classify provenance → decide → audit write-ahead → (gateway|None)."""
        if local_available is None:
            local_available = self._local_healthy()
        data_class = self.egress.classify(provenances)
        decision = self.egress.decide(
            data_class, local_available=local_available,
            claude_available=self.claude_gateway is not None)
        intent = self.audit.record_intent(
            tenant_id=ctx.tenant_id, actor=ctx.subject or actor, action=action, resource="case",
            trace_id=trace_id, data_class=data_class.value,
            residency=ctx.residency_region, llm_destination=decision.destination.value)
        if self.metrics is not None:
            self.metrics.inc("traluat_requests_total", tenant=ctx.tenant_id, action=action)
            self.metrics.inc("traluat_route_total", dest=decision.destination.value)
            if decision.destination.value == "deny":
                self.metrics.inc("traluat_egress_denied_total", tenant=ctx.tenant_id)
        return decision, intent, self._gateway_for(decision.destination)

    def analyze(
        self, case: CaseInput, as_of: dt.date, ctx: TenantContext, *,
        local_available: bool | None = None,   # B5: None → health-probe (không tin client)
        actor: str = "api",
        trace_id: str | None = None,
        lang: str = "vi",
    ) -> ServiceResponse:
        trace_id = trace_id or uuid.uuid4().hex   # bất biến (2): luôn có trace_id
        # I3: tình tiết vụ việc là VĂN BẢN KHÁCH → LUÔN client_sensitive (tag tại intake).
        provenances = [f"tenant:{ctx.tenant_id}", PUBLIC_KB]
        decision, intent, gateway = self._route(
            ctx, provenances, "analyze", local_available, trace_id, actor)
        if gateway is None:
            self.audit.confirm(intent, "denied")
            return ServiceResponse(False, trace_id, decision,
                                   reason=f"egress_denied:{decision.reason}")
        engine = ReasoningEngine(
            self.s, gateway=gateway, nli=self.nli,
            element_judge=self.element_judge, elements_by_eid=self.elements_by_eid,
            retriever=self.retriever)
        try:
            with span("service.analyze", trace_id=trace_id,
                      **{"traluat.destination": decision.destination.value}):
                adj = engine.analyze(case, as_of, tenant_id=ctx.tenant_id, lang=lang)
        except LocalModelError as exc:
            self.audit.confirm(intent, "failed")
            return ServiceResponse(False, trace_id, decision, reason=str(exc))
        self.audit.confirm(intent, "done")
        return ServiceResponse(True, trace_id, decision, adjudication=adj)

    def lookup(
        self, query: str, as_of: dt.date, ctx: TenantContext, *,
        local_available: bool | None = None, actor: str = "api",
        trace_id: str | None = None, lang: str = "vi",
        scope_frbr_uris: list[str] | None = None,
    ) -> ServiceResponse:
        """Free-text client questions default to tenant-sensitive regardless of topic."""
        trace_id = trace_id or uuid.uuid4().hex
        decision, intent, gateway = self._route(
            ctx, [f"tenant:{ctx.tenant_id}", PUBLIC_KB], "lookup", local_available, trace_id, actor)
        if gateway is None:
            self.audit.confirm(intent, "denied")
            return ServiceResponse(False, trace_id, decision,
                                   reason=f"egress_denied:{decision.reason}")
        try:
            ans = answer_question(self.s, query, as_of=as_of, gateway=gateway,
                                  nli=self.nli, tenant_id=ctx.tenant_id, lang=lang,
                                  retriever=self.retriever, scope_frbr_uris=scope_frbr_uris)
        except LocalModelError as exc:
            self.audit.confirm(intent, "failed")
            return ServiceResponse(False, trace_id, decision,
                                   answer=Answer.abstained(str(exc), as_of), reason=str(exc))
        self.audit.confirm(intent, "done")
        return ServiceResponse(not ans.abstain, trace_id, decision, answer=ans,
                               reason=ans.reason)

    def summarize(
        self, topic: str, as_of: dt.date, ctx: TenantContext, *,
        local_available: bool | None = None, actor: str = "api",
        trace_id: str | None = None, lang: str = "vi",
    ) -> ServiceResponse:
        """FR-14 — Tóm tắt quy định pháp luật về `topic`@as_of (KB công, grounded,
        cite-or-abstain). node='summary' → model-tier router. Egress như lookup."""
        trace_id = trace_id or uuid.uuid4().hex
        decision, intent, gateway = self._route(
            ctx, [f"tenant:{ctx.tenant_id}", PUBLIC_KB], "summarize", local_available, trace_id, actor)
        if gateway is None:
            self.audit.confirm(intent, "denied")
            return ServiceResponse(False, trace_id, decision,
                                   reason=f"egress_denied:{decision.reason}")
        try:
            ans = answer_question(
                self.s, f"Tóm tắt các quy định pháp luật về: {topic}", as_of=as_of,
                gateway=gateway, nli=self.nli, tenant_id=ctx.tenant_id, lang=lang,
                node="summary", retriever=self.retriever)
        except LocalModelError as exc:
            self.audit.confirm(intent, "failed")
            return ServiceResponse(False, trace_id, decision,
                                   answer=Answer.abstained(str(exc), as_of), reason=str(exc))
        self.audit.confirm(intent, "done")
        return ServiceResponse(not ans.abstain, trace_id, decision, answer=ans,
                               reason=ans.reason)

    # ── Dịch vụ nghiệp vụ (W6) — vỏ egress/audit, endpoint KHÔNG tự new service ──
    def draft(self, kind: str, facts: str, as_of: dt.date, ctx: TenantContext, *,
              lang: str = "vi", actor: str = "api"):
        """FR-34 soạn đơn. Tình tiết khách → egress LOCAL (R2 no-failover). Trả
        (DraftResult, trace_id)."""
        from ..w6 import DraftResult, PetitionDraftService
        trace_id = uuid.uuid4().hex
        _decision, intent, gateway = self._route(
            ctx, [f"tenant:{ctx.tenant_id}", PUBLIC_KB], "draft", None, trace_id, actor)
        if gateway is None:                       # local down → không fallback
            self.audit.confirm(intent, "denied")
            return DraftResult(True, reason="local_unavailable"), trace_id
        try:
            d = PetitionDraftService(self.s, gateway=gateway, nli=self.nli,
                                     retriever=self.retriever).draft(
                kind, facts, as_of, tenant_id=ctx.tenant_id, lang=lang)
        except LocalModelError as exc:
            self.audit.confirm(intent, "failed")
            return DraftResult(True, reason=str(exc)), trace_id
        self.audit.confirm(intent, "done")
        return d, trace_id

    def advise(self, activity: str, as_of: dt.date, ctx: TenantContext, *,
               lang: str = "vi", actor: str = "api"):
        """FR-08 tư vấn tuân thủ. Hoạt động khách → egress LOCAL. Trả (AdvisoryResult, tid)."""
        from ..w6 import AdvisoryResult, ComplianceAdvisoryService
        trace_id = uuid.uuid4().hex
        _decision, intent, gateway = self._route(
            ctx, [f"tenant:{ctx.tenant_id}", PUBLIC_KB], "advise", None, trace_id, actor)
        if gateway is None:
            self.audit.confirm(intent, "denied")
            return AdvisoryResult(True, reason="local_unavailable"), trace_id
        try:
            a = ComplianceAdvisoryService(self.s, gateway=gateway, nli=self.nli,
                                         retriever=self.retriever).advise(
                activity, as_of, tenant_id=ctx.tenant_id, lang=lang)
        except LocalModelError as exc:
            self.audit.confirm(intent, "failed")
            return AdvisoryResult(True, reason=str(exc)), trace_id
        self.audit.confirm(intent, "done")
        return a, trace_id

    def judgment(self, cited_eids, expected_governing, as_of: dt.date, ctx: TenantContext,
                 *, cited_precedents=None, actor: str = "api"):
        """FR-03 second-opinion. CN-03 high-risk → BẮT BUỘC audit. Trả (JudgmentFinding, tid)."""
        from ..w6 import JudgmentAnalysisService
        trace_id = uuid.uuid4().hex
        intent = self.audit.record_intent(
            tenant_id=ctx.tenant_id, actor=ctx.subject or actor, action="judgment",
            resource="case", trace_id=trace_id, data_class=PUBLIC_KB,
            residency=ctx.residency_region, llm_destination="none",
        )
        f = JudgmentAnalysisService(self.s).analyze(
            cited_eids, expected_governing, as_of, cited_precedents=cited_precedents)
        self.audit.confirm(intent, "done")
        return f, trace_id

    # ── Đọc KB công (không model, không dữ-liệu-khách) — vỏ mỏng ──
    def compare(self, frbr: str, a: dt.date, b: dt.date, lang: str = "vi"):
        from ..w6 import ComplianceDiffService
        return ComplianceDiffService(self.s).diff(frbr, a, b, lang)

    def analyze_case(self, facts: str, parties, as_of: dt.date, ctx: TenantContext, **kw):
        """Vỏ tiện: endpoint truyền facts+parties thô, không chạm CaseInput (W4)."""
        return self.analyze(CaseInput(facts=facts, parties=parties or []), as_of, ctx, **kw)

    def review(self, text: str, rule_dicts):
        from ..w6 import RequiredClauseRule, ReviewService
        rules = [RequiredClauseRule(**r) for r in rule_dicts]
        return ReviewService().review(text, rules)

    def deadline(self, kind: str, start: dt.date, as_of: dt.date):
        from ..tools.deadlines import compute_deadline
        return compute_deadline(self.s, kind, start, as_of)

    def document_as_of(self, frbr: str, as_of: dt.date):
        from ..w2 import repo
        return repo.document_as_of(self.s, frbr, as_of)

    def nearby(self, lat: float, lon: float, radius_m: float, *, kind=None):
        from ..tools.directory import nearby
        return nearby(self.s, lat, lon, radius_m, kind=kind)

    def neighborhood(self, eid: str, as_of, hops: int):
        from ..w2 import repo
        return repo.neighborhood(self.s, eid, as_of, max_hops=min(hops, 3))

    def graph_central(self, driver):
        if driver is None:
            return {}
        from ..w2.graph_neo4j import gds_pagerank
        return dict(gds_pagerank(driver))

    def review_queue(self):
        from ..core.knowledge_ops import pending_relations
        return pending_relations(self.s)

    def approve_relation(self, rel_id: int, ctx: TenantContext):
        if not ctx.platform_operator:
            raise PermissionError("platform operator required")
        if self.knowledge_session_factory is None:
            raise RuntimeError("knowledge administration connection is not configured")
        import sqlalchemy as sa

        from ..core.knowledge_ops import approve_relation
        from ..w2.models import Document, Unit, UnitVersion
        from ..w2.repo import materialize
        from ..w3.indexer import reindex_document
        from ..w3.retrieval import IndexedRetriever

        trace_id = uuid.uuid4().hex
        intent = self.audit.record_intent(
            tenant_id=ctx.tenant_id, actor=ctx.subject or "operator",
            action="approve_relation", resource=f"relation:{rel_id}", trace_id=trace_id,
            data_class=PUBLIC_KB, residency=ctx.residency_region, llm_destination="none",
        )
        with self.knowledge_session_factory() as session, session.begin():
            rel = approve_relation(session, rel_id)
            applied = materialize(session, rel)
            if (applied and rel.relation_type in {"repeals", "replaces"}
                    and isinstance(self.retriever, IndexedRetriever)):
                doc = session.get(Document, rel.dst_doc_id)
                langs = session.scalars(sa.select(UnitVersion.lang).join(Unit).where(
                    Unit.document_id == doc.id).distinct()).all()
                for lang in langs:
                    reindex_document(session, doc.frbr_uri, lang=lang,
                                     embedder=self.retriever.embedder)
        self.audit.confirm(intent, "done")
        return applied
