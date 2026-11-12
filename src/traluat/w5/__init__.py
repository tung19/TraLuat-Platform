"""W5 — Backend serving (slice-1: lõi bảo mật tất định).

Moat vận hành (ship-blocker C1–C6): tenancy guard + EgressPolicy (dữ liệu khách
KHÔNG rời VN, fail-closed, R2 không-failover) + audit write-ahead + nhãn AI/trace_id.
FastAPI/Celery/RLS (infra lift PAKTON) cắm trên lõi này sau. Spec: docs/specs/w5-backend.md.
"""

from .audit import AuditEntry, AuditLog, PostgresAuditLog
from .auth import decode_context
from .crypto import (
    AwsKmsProvider,
    CryptoShredded,
    KMSProvider,
    RemoteKMSProvider,
    SoftwareKMS,
    TenantCrypto,
    VaultTransitProvider,
)
from .egress import DataClass, EgressPolicy, LLMDestination, RouteDecision
from .models import AnalysisTask, AuditLogRow, Tenant, TenantUser
from .rls import rls_ddl, set_tenant
from .service import LegalService, ServiceResponse
from .tasks import CeleryTaskQueue, InMemoryTaskQueue, TaskQueue, TaskRunner
from .tenancy import MissingTenant, ResidencyViolation, TenantContext, require_role

__all__ = [
    "AnalysisTask",
    "AuditEntry",
    "AuditLog",
    "AuditLogRow",
    "AwsKmsProvider",
    "CeleryTaskQueue",
    "CryptoShredded",
    "DataClass",
    "EgressPolicy",
    "InMemoryTaskQueue",
    "KMSProvider",
    "LLMDestination",
    "LegalService",
    "MissingTenant",
    "PostgresAuditLog",
    "RemoteKMSProvider",
    "ResidencyViolation",
    "RouteDecision",
    "ServiceResponse",
    "SoftwareKMS",
    "TaskQueue",
    "TaskRunner",
    "Tenant",
    "TenantContext",
    "TenantCrypto",
    "TenantUser",
    "VaultTransitProvider",
    "decode_context",
    "require_role",
    "rls_ddl",
    "set_tenant",
]
