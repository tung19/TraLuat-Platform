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
