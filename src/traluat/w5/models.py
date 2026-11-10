"""W5 client-plane models (L2/P2) — tenant + RBAC + audit, TÁCH khỏi KB (W2).

Bảng DỮ LIỆU KHÁCH mang `tenant_id` + chịu FORCE ROW LEVEL SECURITY (migration
0006). audit_log = append-only (role chỉ INSERT). Dùng chung Base với W2 để alembic
thấy; nhưng về ngữ nghĩa là lớp isolation khác (KB shared read-only vs client isolated).
"""

from __future__ import annotations

import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..w2.models import Base


class Tenant(Base):
    __tablename__ = "tenant"
    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="active")          # active | suspended
    isolation_mode: Mapped[str] = mapped_column(default="rls")     # rls | schema
    residency_region: Mapped[str] = mapped_column(default="vn")
    retention_mode: Mapped[str] = mapped_column(default="standard")  # standard | zero
    kms_key_id: Mapped[str | None]
    created_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now())


class TenantUser(Base):
    __tablename__ = "tenant_user"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("tenant.id"), index=True)
    email: Mapped[str]
    role: Mapped[str] = mapped_column(default="viewer")           # owner|lawyer|reviewer|viewer
    __table_args__ = (sa.UniqueConstraint("tenant_id", "email", name="uq_tenant_user"),)


class AuditLogRow(Base):
    """Bảng khách — mang tenant_id, FORCE RLS, append-only (chỉ INSERT)."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    actor: Mapped[str | None]
    action: Mapped[str | None]
    resource: Mapped[str | None]
    trace_id: Mapped[str | None] = mapped_column(index=True)
    phase: Mapped[str | None]
    data_class: Mapped[str | None]
    residency: Mapped[str | None]
    llm_destination: Mapped[str | None]
    ts: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now())
    meta: Mapped[dict | None] = mapped_column(JSONB)


class AlertSubscription(Base):
    """FR-09 — theo dõi 1 văn bản; luật đổi → sinh Alert. Bảng khách (RLS)."""
    __tablename__ = "alert_subscription"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    frbr_uri: Mapped[str] = mapped_column(index=True)
    channel: Mapped[str] = mapped_column(default="record")   # record|webhook|email
    target: Mapped[str | None]                               # URL webhook / email


class Alert(Base):
    __tablename__ = "alert"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    frbr_uri: Mapped[str]
    change: Mapped[str]                                      # repealed|replaced|amended
    detail: Mapped[str | None]
    created_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now())
    delivered: Mapped[bool] = mapped_column(default=False)


class AnalysisTask(Base):
    """Task bất đồng bộ — bảng khách, tenant_id + FORCE RLS → /tasks/{id} chống IDOR
    (C6): fetch task tenant khác → RLS trả rỗng (không thấy)."""
    __tablename__ = "analysis_task"
    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    kind: Mapped[str]                                  # analyze | lookup
    status: Mapped[str] = mapped_column(default="queued")   # queued|running|done|error
    payload: Mapped[dict | None] = mapped_column(JSONB)     # input để worker tái dựng job
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None]
    created_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now())
