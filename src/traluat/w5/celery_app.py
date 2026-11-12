"""Celery worker (W5 §1) — xử lý nặng async, warm per-worker, retry hạ-tầng.

Broker/backend từ env (RabbitMQ/Redis); eager fallback (memory) cho dev/test. Worker
KHÔNG dính state per-request (tenant truyền qua payload, không global). Retry lỗi
hạ-tầng (max 3), KHÔNG retry 4xx/validation. Body tách (`run_task_body`) để test với
session kiểm, không cần broker.

Chạy worker: `celery -A traluat.w5.celery_app.celery_app worker -l info`
"""

from __future__ import annotations

import os
from collections.abc import Callable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .models import AnalysisTask
from .rls import ensure_runtime_login, set_tenant

# handler đăng ký theo kind: (session, payload) -> dict (result)
_HANDLERS: dict[str, Callable[[Session, dict], dict]] = {}


def register_handler(kind: str, fn: Callable[[Session, dict], dict]) -> None:
    _HANDLERS[kind] = fn


def run_task_body(session: Session, task_id, tenant_id: str, *,
                  app_role: str | None = "traluat_app") -> str:
    """Logic worker (test được với session kiểm). tenant_id đi kèm task_id để set
    RLS TRƯỚC khi đọc (không thể đọc task dưới RLS nếu chưa set tenant). Trả status."""
    if app_role:
        session.execute(sa.text(f"SET LOCAL ROLE {app_role}"))
    set_tenant(session, tenant_id)      # set TRƯỚC → RLS cho đọc task của tenant này
    task = session.scalars(sa.select(AnalysisTask).where(AnalysisTask.id == task_id)).first()
    if task is None:
        return "not_found"
    handler = _HANDLERS.get(task.kind)
    if handler is None:
        task.status, task.error = "error", f"no handler: {task.kind}"
        session.flush()
        return task.status
    try:
        task.status = "running"; session.flush()
        task.result = handler(session, task.payload or {})
        task.status = "done"
    except Exception as e:  # noqa: BLE001
        task.status, task.error = "error", str(e)
    session.flush()
    return task.status


def _make_celery():
    try:
        from celery import Celery
    except ImportError:  # pragma: no cover
        return None
    broker = os.environ.get("CELERY_BROKER_URL", "memory://")
    backend = os.environ.get("CELERY_RESULT_BACKEND", "cache+memory://")
    app = Celery("traluat", broker=broker, backend=backend)
    app.conf.task_always_eager = (
        os.environ.get("CELERY_TASK_ALWAYS_EAGER") == "1" or broker == "memory://")

    @app.task(bind=True, name="traluat.run_task", max_retries=3, default_retry_delay=5)
    def run_task(self, task_id: str, tenant_id: str):  # pragma: no cover — prod shell
        from ..w2.db import make_session_factory
        s = make_session_factory()()
        try:
            ensure_runtime_login(s)
            status = run_task_body(s, task_id, tenant_id)
            s.commit()
            return status
        except (sa.exc.OperationalError, sa.exc.InterfaceError, ConnectionError, TimeoutError) as e:
            s.rollback()
            raise self.retry(exc=e)
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    app.run_task = run_task
    return app


celery_app = _make_celery()
