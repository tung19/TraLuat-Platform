"""Async task layer (W5 §1/§6) — port + eager stub + Celery skeleton + RLS IDOR.

TaskRunner: tạo task row (tenant_id, FORCE RLS) → chạy work → cập nhật status/result.
get() set_tenant rồi SELECT (không dùng Session.get — tránh identity-map bypass RLS)
→ fetch task tenant khác trả None (C6 chống IDOR). InMemoryTaskQueue = eager (sync,
test được); CeleryTaskQueue = skeleton (worker thật rebuild session — cắm sau).
"""

from __future__ import annotations

import uuid
from typing import Callable, Protocol, runtime_checkable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .models import AnalysisTask
from .rls import set_tenant
from .tenancy import TenantContext


@runtime_checkable
class TaskQueue(Protocol):
    def submit(self, run: Callable[[], None]) -> None: ...


class InMemoryTaskQueue:
    """Eager — chạy ngay (đồng bộ). Dùng test + dev; prod dùng CeleryTaskQueue."""
    def submit(self, run: Callable[[], None]) -> None:
        run()


class CeleryTaskQueue:
    """Skeleton — prod: @celery task rebuild session + chạy work. Cần broker (env)."""
    def __init__(self, celery_app=None) -> None:
        self._app = celery_app

    def submit(self, run: Callable[[], None]) -> None:  # noqa: ARG002
        raise NotImplementedError(
            "CeleryTaskQueue: đăng ký @app.task(rebuild session) + send_task — cắm khi có broker")


class TaskRunner:
    def __init__(self, session: Session, queue: TaskQueue | None = None,
                 app_role: str | None = "traluat_app") -> None:
        self.s = session
        self.queue = queue or InMemoryTaskQueue()
        # ★ RLS chỉ áp khi KHÔNG phải superuser (superuser bypass kể cả FORCE).
        # Prod connect sẵn bằng traluat_app; dev/superuser → SET LOCAL ROLE.
        self.app_role = app_role

    def _use_role(self) -> None:
        if self.app_role:
            self.s.execute(sa.text(f"SET LOCAL ROLE {self.app_role}"))

    def submit(self, ctx: TenantContext, kind: str, work: Callable[[], dict]) -> uuid.UUID:
        self._use_role()
        set_tenant(self.s, ctx.tenant_id)
        task = AnalysisTask(tenant_id=uuid.UUID(ctx.tenant_id), kind=kind, status="queued")
        self.s.add(task)
        self.s.flush()
        tid = task.id

        def _run() -> None:
            self._use_role()
            set_tenant(self.s, ctx.tenant_id)
            t = self.s.get(AnalysisTask, tid)
            try:
                t.status = "running"
                self.s.flush()
                t.result = work()
                t.status = "done"
            except Exception as e:  # noqa: BLE001
                t.status, t.error = "error", str(e)
            self.s.flush()

        self.queue.submit(_run)
        return tid

    def get(self, ctx: TenantContext, task_id) -> AnalysisTask | None:
        self._use_role()
        set_tenant(self.s, ctx.tenant_id)   # RLS → chỉ task của tenant này
        self.s.expire_all()                 # bỏ identity-map → SELECT chạm DB, RLS áp
        return self.s.scalars(
            sa.select(AnalysisTask).where(AnalysisTask.id == task_id)).first()
