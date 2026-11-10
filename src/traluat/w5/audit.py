"""Audit log (C5 + NĐ 356 Đ29) — append-only, ghi QUYẾT ĐỊNH route/egress (không
nội dung). Write-ahead: ghi 'intent' TRƯỚC khi gọi, 'confirm' SAU → crash giữa chừng
vẫn còn bằng chứng dữ liệu khách ở lại VN. Giữ ≥5 năm (persist layer cắm sau)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class AuditEntry:
    tenant_id: str
    actor: str
    action: str
    resource: str
    trace_id: str
    phase: str                    # 'intent' | 'done' | 'denied'
    data_class: str | None = None
    residency: str = "vn"
    llm_destination: str | None = None
    ts: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    meta: dict = field(default_factory=dict)


class AuditLog:
    """Append-only (in-memory stub; cắm DB INSERT-only sau). KHÔNG mutate entry cũ."""

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record_intent(
        self, *, tenant_id: str, actor: str, action: str, resource: str,
        trace_id: str, data_class: str, residency: str, llm_destination: str,
    ) -> AuditEntry:
        e = AuditEntry(tenant_id, actor, action, resource, trace_id, "intent",
                       data_class, residency, llm_destination)
        self.entries.append(e)      # write-ahead: trước khi gọi LLM
        return e

    def confirm(self, intent: AuditEntry, phase: str) -> AuditEntry:
        # append bản xác nhận MỚI (không sửa 'intent' — append-only)
        e = AuditEntry(intent.tenant_id, intent.actor, intent.action, intent.resource,
                       intent.trace_id, phase, intent.data_class, intent.residency,
                       intent.llm_destination)
        self.entries.append(e)
        return e

    def by_trace(self, trace_id: str) -> list[AuditEntry]:
        return [e for e in self.entries if e.trace_id == trace_id]


class PostgresAuditLog:
    """Audit append-only PERSIST vào bảng audit_log (FORCE RLS). Drop-in cho AuditLog.

    Phiên PHẢI set_tenant trước (RLS + role non-owner) — get_tenant_db_session lo.
    tenant_id phải là uuid (TenantContext của tenant thật)."""

    def __init__(self, session) -> None:
        self.s = session

    def record_intent(
        self, *, tenant_id: str, actor: str, action: str, resource: str,
        trace_id: str, data_class: str, residency: str, llm_destination: str,
    ):
        import uuid as _uuid

        from .models import AuditLogRow
        row = AuditLogRow(
            tenant_id=_uuid.UUID(tenant_id), actor=actor, action=action, resource=resource,
            trace_id=trace_id, phase="intent", data_class=data_class, residency=residency,
            llm_destination=llm_destination)
        self.s.add(row)
        self.s.flush()
        return row

    def confirm(self, intent, phase: str):
        from .models import AuditLogRow
        row = AuditLogRow(
            tenant_id=intent.tenant_id, actor=intent.actor, action=intent.action,
            resource=intent.resource, trace_id=intent.trace_id, phase=phase,
            data_class=intent.data_class, residency=intent.residency,
            llm_destination=intent.llm_destination)
        self.s.add(row)
        self.s.flush()
        return row

    def by_trace(self, trace_id: str):
        import sqlalchemy as sa

        from .models import AuditLogRow
        return list(self.s.scalars(
            sa.select(AuditLogRow).where(AuditLogRow.trace_id == trace_id)))
