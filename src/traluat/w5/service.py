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

from ..w3.ports import LLMGateway, NLIVerifier
from ..w4 import Adjudication, CaseInput, ReasoningEngine
from ..w4.auditor import ElementJudge
from .audit import AuditLog
from .egress import PUBLIC_KB, EgressPolicy, LLMDestination, RouteDecision
from .tenancy import TenantContext


@dataclass
class ServiceResponse:
    answered: bool
    trace_id: str
    route: RouteDecision
    ai_label: bool = True                 # Luật 71/2025 — luôn gắn
    adjudication: Adjudication | None = None
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
    ) -> None:
        self.s = session
        self.local_gateway = local_gateway
        self.claude_gateway = claude_gateway
        self.nli = nli
        self.element_judge = element_judge
        self.elements_by_eid = elements_by_eid
        self.egress = egress or EgressPolicy()
        self.audit = audit or AuditLog()

    def _gateway_for(self, dest: LLMDestination) -> LLMGateway | None:
        if dest == LLMDestination.LOCAL:
            return self.local_gateway
        if dest == LLMDestination.CLAUDE:
            return self.claude_gateway
        return None

    def _local_healthy(self) -> bool:
        fn = getattr(self.local_gateway, "healthy", None)
        return bool(fn()) if callable(fn) else True

    def analyze(
        self, case: CaseInput, as_of: dt.date, ctx: TenantContext, *,
        client_data: bool = True,          # tình tiết do khách cung cấp → sensitive
        local_available: bool | None = None,   # B5: None → health-probe gateway (không tin client)
        actor: str = "api",
        trace_id: str | None = None,
        lang: str = "vi",
    ) -> ServiceResponse:
        trace_id = trace_id or uuid.uuid4().hex   # bất biến (2): luôn có trace_id
        if local_available is None:
            local_available = self._local_healthy()

        # provenance tất định (không đoán nội dung): KB công + (nếu có) upload khách
        provenances = ([f"tenant:{ctx.tenant_id}"] if client_data else []) + [PUBLIC_KB]
        data_class = self.egress.classify(provenances)
        decision = self.egress.decide(
            data_class, local_available=local_available,
            claude_available=self.claude_gateway is not None,
        )

        intent = self.audit.record_intent(      # write-ahead TRƯỚC khi gọi
            tenant_id=ctx.tenant_id, actor=actor, action="analyze", resource="case",
            trace_id=trace_id, data_class=data_class.value,
            residency=ctx.residency_region, llm_destination=decision.destination.value,
        )

        gateway = self._gateway_for(decision.destination)
        if gateway is None:                       # DENY (R2 local-down) hoặc thiếu claude
            self.audit.confirm(intent, "denied")
            return ServiceResponse(False, trace_id, decision,
                                   reason=f"egress_denied:{decision.reason}")

        engine = ReasoningEngine(
            self.s, gateway=gateway, nli=self.nli,
            element_judge=self.element_judge, elements_by_eid=self.elements_by_eid,
        )
        adj = engine.analyze(case, as_of, tenant_id=ctx.tenant_id, lang=lang)
        self.audit.confirm(intent, "done")
        return ServiceResponse(True, trace_id, decision, adjudication=adj)
