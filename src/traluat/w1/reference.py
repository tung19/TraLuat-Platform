"""Reference-data adapter (luồng 3) — Lakehouse→canonical, PII gate, idempotent upsert.

Đội data đẩy dataset theo schema; adapter: quét PII (quarantine-by-default, F5 — gate
DÙNG CHUNG mọi luồng nạp) + upsert idempotent theo (dataset,key,valid_from,version).
Phục vụ qua RULE tier (lookup_reference) — hiệu-lực-aware, KHÔNG model.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..w2.models import ReferenceValue

# PII tiếng Việt (tối thiểu): CCCD 12 số · điện thoại · email.
_PII = [
    re.compile(r"\b\d{12}\b"),              # CCCD
    re.compile(r"\b0\d{9}\b"),              # số điện thoại
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),  # email
]


def has_pii(text: str) -> bool:
    return any(p.search(text) for p in _PII)


@dataclass
class RefRow:
    key: str
    value: dict
    valid_from: dt.date
    valid_to: dt.date | None = None
    source_eid: str | None = None          # neo điều luật (dataset suy-từ-luật)


@dataclass
class RefOutcome:
    loaded: int = 0
    quarantined: list[str] = None          # key bị giữ do PII

    def __post_init__(self):
        if self.quarantined is None:
            self.quarantined = []


def upsert_reference(
    session: Session, dataset: str, rows: list[RefRow], *, version: str = "v1",
    pii_check: bool = True,
) -> RefOutcome:
    """Nạp 1 mẻ reference. PII → quarantine (không upsert). Idempotent theo khoá.

    pii_check: dataset SỐ (muc_phat/thue — giá trị tiền nhiều chữ số) đặt False để
    tránh false-positive (số tiền 12 chữ số ≈ CCCD). Dataset có liên hệ (danh bạ) giữ True.
    """
    out = RefOutcome()
    for r in rows:
        blob = r.key + " " + json.dumps(r.value, ensure_ascii=False)
        if pii_check and has_pii(blob):
            out.quarantined.append(r.key)   # F5: giữ lại, không đổ vào store
            continue
        stmt = pg_insert(ReferenceValue).values(
            dataset=dataset, key=r.key, value=r.value, valid_from=r.valid_from,
            valid_to=r.valid_to, source_eid=r.source_eid, version=version)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_refval",
            set_={"value": r.value, "valid_to": r.valid_to, "source_eid": r.source_eid})
        session.execute(stmt)
        out.loaded += 1
    session.flush()
    return out


def lookup_reference(
    session: Session, dataset: str, key: str, as_of: dt.date,
) -> ReferenceValue | None:
    """RULE tier — giá trị HIỆU-LỰC tại as_of (moat: calculator có-nguồn-luật)."""
    return session.scalars(
        sa.select(ReferenceValue).where(
            ReferenceValue.dataset == dataset, ReferenceValue.key == key,
            ReferenceValue.valid_from <= as_of,
            sa.or_(ReferenceValue.valid_to.is_(None), as_of < ReferenceValue.valid_to))
        .order_by(ReferenceValue.valid_from.desc()).limit(1)).first()
