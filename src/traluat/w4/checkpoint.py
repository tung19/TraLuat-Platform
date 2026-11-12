"""Durable checkpointer (W4 §5.3) — resume vòng đa vai, tenant-aware.

★ C3 (W5 spec): checkpointer dùng POOL RIÊNG → RLS KHÔNG với tới. Bảo vệ ở
application: thread_id = `tenant:<id>:<case>` và VALIDATE prefix mỗi read/write.
State lưu eid (không object) → nạp lại Article từ W2. H4 persist: điều đã verify
ở lần trước KHÔNG audit lại khi resume (seed memo).
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
from typing import Protocol, runtime_checkable

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..w2.models import Base, Document, NormRelation, PrecedentRow, Unit, UnitVersion


def knowledge_fingerprint(session) -> str:
    """Bind resumed audits to canonical content, including in-place edge reviews.

    Checkpointing is optional; favour correctness over a stale global cache.
    A durable KB revision service may replace this full digest once available.
    """
    session.flush()
    digest = hashlib.sha256()
    for model in (Document, Unit, UnitVersion, NormRelation, PrecedentRow):
        table = model.__table__
        digest.update(table.name.encode())
        for row in session.execute(sa.select(*table.columns).order_by(table.c.id)):
            digest.update(json.dumps(list(row), ensure_ascii=False, default=str,
                                     separators=(",", ":")).encode())
            digest.update(b"\n")
    return digest.hexdigest()


class CrossTenantCheckpoint(RuntimeError):
    """thread_id không khớp prefix tenant hiện tại → chặn (chống rò chéo)."""


def _check_prefix(thread_id: str, tenant_id: str) -> None:
    if not thread_id.startswith(f"tenant:{tenant_id}:"):
        raise CrossTenantCheckpoint(f"thread_id {thread_id!r} ≠ tenant {tenant_id!r}")


@runtime_checkable
class Checkpointer(Protocol):
    def save(self, thread_id: str, tenant_id: str, state: dict) -> None: ...
    def load(self, thread_id: str, tenant_id: str) -> dict | None: ...


class InMemoryCheckpointer:
    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def save(self, thread_id: str, tenant_id: str, state: dict) -> None:
        _check_prefix(thread_id, tenant_id)
        self._store[thread_id] = copy.deepcopy(state)

    def load(self, thread_id: str, tenant_id: str) -> dict | None:
        _check_prefix(thread_id, tenant_id)
        s = self._store.get(thread_id)
        return copy.deepcopy(s) if s is not None else None


class DebateCheckpoint(Base):
    __tablename__ = "debate_checkpoint"
    thread_id: Mapped[str] = mapped_column(primary_key=True)
    tenant_id: Mapped[str]
    state: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now())


class PostgresCheckpointer:
    def __init__(self, session) -> None:
        self.s = session

    def save(self, thread_id: str, tenant_id: str, state: dict) -> None:
        _check_prefix(thread_id, tenant_id)
        row = self.s.get(DebateCheckpoint, thread_id)
        if row is None:
            self.s.add(DebateCheckpoint(thread_id=thread_id, tenant_id=tenant_id, state=state))
        else:
            row.state = state
            row.updated_at = dt.datetime.now(dt.UTC)
        self.s.flush()

    def load(self, thread_id: str, tenant_id: str) -> dict | None:
        _check_prefix(thread_id, tenant_id)
        row = self.s.get(DebateCheckpoint, thread_id)
        return dict(row.state) if row is not None else None
