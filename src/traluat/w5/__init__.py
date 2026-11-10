"""W5 — Backend serving (slice-1: lõi bảo mật tất định).

Moat vận hành (ship-blocker C1–C6): tenancy guard + EgressPolicy (dữ liệu khách
KHÔNG rời VN, fail-closed, R2 không-failover) + audit write-ahead + nhãn AI/trace_id.
FastAPI/Celery/RLS (infra lift PAKTON) cắm trên lõi này sau. Spec: docs/specs/w5-backend.md.
"""

from .tenancy import MissingTenant, ResidencyViolation, TenantContext, require_role
from .egress import DataClass, EgressPolicy, LLMDestination, RouteDecision
from .audit import AuditEntry, AuditLog
from .service import LegalService, ServiceResponse
from .auth import decode_context
from .rls import rls_ddl, set_tenant

__all__ = [
    "TenantContext", "MissingTenant", "ResidencyViolation", "require_role",
    "EgressPolicy", "DataClass", "LLMDestination", "RouteDecision",
    "AuditLog", "AuditEntry",
    "LegalService", "ServiceResponse",
    "decode_context", "rls_ddl", "set_tenant",
]
