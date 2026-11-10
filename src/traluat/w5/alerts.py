"""FR-09 Alert pipeline — luật đổi (materialize) → fan-out tới người theo dõi.

Hook sau materialize (như Neo4j sync): quan hệ repeals/replaces/amends được áp →
tìm subscriber của VĂN BẢN ĐÍCH → sinh Alert + deliver. Deliverer port: Recording
(test) · Webhook/Email (skeleton, cần endpoint/SMTP). RLS cô lập alert theo tenant.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..w2.models import Document
from .models import Alert, AlertSubscription

_CHANGE = {"repeals": "repealed", "replaces": "replaced", "amends": "amended"}


@runtime_checkable
class Deliverer(Protocol):
    def deliver(self, alert: Alert) -> None: ...


class RecordingDeliverer:
    def __init__(self) -> None:
        self.records: list[Alert] = []

    def deliver(self, alert: Alert) -> None:
        self.records.append(alert)


class WebhookDeliverer:
    """Skeleton — POST payload tới URL subscriber (cần endpoint khách)."""
    def __init__(self, post_fn) -> None:
        self._post = post_fn

    def deliver(self, alert: Alert) -> None:  # pragma: no cover
        self._post({"frbr": alert.frbr_uri, "change": alert.change, "detail": alert.detail})


def subscribe(session: Session, tenant_id, frbr_uri: str, *,
              channel: str = "record", target: str | None = None) -> AlertSubscription:
    sub = AlertSubscription(tenant_id=tenant_id, frbr_uri=frbr_uri, channel=channel, target=target)
    session.add(sub)
    session.flush()
    return sub


def fan_out(session: Session, rel, *, deliverer: Deliverer | None = None) -> list[Alert]:
    """Sinh Alert cho mọi subscriber của VB đích của quan hệ; deliver nếu có."""
    frbr = session.scalar(sa.select(Document.frbr_uri).where(Document.id == rel.dst_doc_id))
    if frbr is None:
        return []
    change = _CHANGE.get(rel.relation_type, rel.relation_type)
    subs = session.scalars(
        sa.select(AlertSubscription).where(AlertSubscription.frbr_uri == frbr)).all()
    out = []
    for sub in subs:
        a = Alert(tenant_id=sub.tenant_id, frbr_uri=frbr, change=change)
        session.add(a)
        session.flush()
        if deliverer is not None:
            deliverer.deliver(a)
            a.delivered = True
        out.append(a)
    session.flush()
    return out


def enable_alert_sync(deliverer: Deliverer | None = None) -> None:
    """Đăng ký hook: materialize quan hệ huỷ/sửa → fan-out alert (option FR-09)."""
    from ..w2 import repo

    def _hook(s, rel):
        if rel.relation_type in _CHANGE:
            fan_out(s, rel, deliverer=deliverer)

    repo.register_post_materialize(_hook)
