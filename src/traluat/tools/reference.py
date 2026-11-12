"""Validated public reference publications, with immutable versions and law anchors.

Unknown datasets require an explicit registered contract. Publication never overwrites
an existing version; a correction uses a new version. Runtime lookup rechecks the law
anchor and deterministically selects the last published applicable row.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..w2.models import ReferenceValue, Unit

_PII = [re.compile(r"\b\d{12}\b"), re.compile(r"\b0\d{9}\b"),
        re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")]


def has_pii(text: str) -> bool:
    return any(pattern.search(text) for pattern in _PII)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


@dataclass
class RefRow:
    key: str
    value: dict
    valid_from: dt.date
    valid_to: dt.date | None = None
    source_eid: str | None = None


@dataclass
class RefOutcome:
    loaded: int = 0
    quarantined: list[str] = field(default_factory=list)
    reasons: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ReferenceContract:
    validate: Callable[[RefRow], None]
    requires_source: bool = False
    numeric_key: bool = False


_CONTRACTS: dict[str, ReferenceContract] = {}


def register_reference_contract(dataset: str, contract: ReferenceContract) -> None:
    """Trusted application configuration; a new dataset cannot publish without a contract."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", dataset):
        raise ValueError("invalid dataset name")
    _CONTRACTS[dataset] = contract


def _number(value, *, minimum=0, maximum=1e15):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("expected a finite number")
    if not minimum <= value <= maximum:
        raise ValueError("number outside dataset contract")


def _numeric_fields(*names, maximum=1e15):
    def validate(row):
        for name in names:
            if name not in row.value:
                raise ValueError(f"missing field: {name}")
            _number(row.value[name], maximum=maximum)
    return validate


def _deadline(row):
    _numeric_fields("value", maximum=10000)(row)
    if not isinstance(row.value["value"], int) or row.value["value"] < 1:
        raise ValueError("deadline must be a positive integer")
    if row.value.get("unit") not in {"day", "month", "year"}:
        raise ValueError("invalid deadline unit")


def _brackets(row):
    brackets = row.value.get("brackets")
    if not isinstance(brackets, list) or not brackets:
        raise ValueError("nonempty brackets required")
    previous = 0
    for i, bracket in enumerate(brackets):
        if not isinstance(bracket, list) or len(bracket) != 2:
            raise ValueError("bracket must be [upper, rate]")
        upper, rate = bracket
        _number(rate, maximum=1)
        if upper is None:
            if i != len(brackets) - 1:
                raise ValueError("unbounded bracket must be last")
        else:
            _number(upper)
            if upper <= previous:
                raise ValueError("bracket bounds must increase")
            previous = upper
    if brackets[-1][0] is not None:
        raise ValueError("final bracket must be unbounded")


def _holidays(row):
    if not re.fullmatch(r"\d{4}", row.key) or not isinstance(row.value.get("dates"), list):
        raise ValueError("holiday year and dates required")
    for value in row.value["dates"]:
        parsed = dt.date.fromisoformat(value)
        if str(parsed.year) != row.key:
            raise ValueError("holiday date outside declared year")


def _tax_id(row):
    if not re.fullmatch(r"\d{10}(?:\d{3})?", row.key):
        raise ValueError("tax identifier must contain 10 or 13 digits")
    if not isinstance(row.value.get("ten"), str) or not row.value["ten"].strip():
        raise ValueError("tax register name required")


def _term(row):
    if row.value.get("vn") != row.key:
        raise ValueError("termbank VN label must equal the key")
    if not any(isinstance(row.value.get(k), str) and row.value[k].strip()
               for k in ("en", "zh", "def")):
        raise ValueError("translation or definition required")


# These are structural/sanity limits, not declarations of Vietnamese legal rates.
for _name in ("thue_suat_tncn", "thue_gtgt", "ty_le_bh", "bieu_thue_xnk"):
    register_reference_contract(_name, ReferenceContract(_numeric_fields("rate", maximum=1), True))
for _name in ("muc_phat", "luong_toi_thieu", "le_phi"):
    register_reference_contract(_name, ReferenceContract(_numeric_fields("muc"), True))
register_reference_contract("lam_them_rate", ReferenceContract(_numeric_fields("rate", maximum=10), True))
register_reference_contract("giam_tru_gia_canh", ReferenceContract(
    _numeric_fields("ban_than", "phu_thuoc"), True))
register_reference_contract("bhxh_he_so", ReferenceContract(
    _numeric_fields("truoc_2014", "tu_2014", maximum=100), True))
register_reference_contract("bieu_thue_tncn", ReferenceContract(_brackets, True))
register_reference_contract("thoi_hieu", ReferenceContract(_deadline, True))
register_reference_contract("ngay_nghi", ReferenceContract(_holidays))
register_reference_contract("ma_so_thue", ReferenceContract(_tax_id, numeric_key=True))
register_reference_contract("termbank", ReferenceContract(_term))
# Generic public directory metadata stays supported, with structural validation and PII scanning.
register_reference_contract("danh_ba", ReferenceContract(lambda row: None))


def _source_applies(session, eid, as_of):
    from ..w2 import repo
    from ..w2.bitemporal import EffectStatus
    return repo.effect_status(session, eid, as_of) in {
        EffectStatus.IN_FORCE, EffectStatus.TRANSITIONAL_APPLIES}


def _validate(session, contract, row):
    if not isinstance(row.key, str) or not row.key.strip() or len(row.key) > 256:
        raise ValueError("nonempty string key required")
    if not isinstance(row.value, dict) or not row.value:
        raise ValueError("nonempty object value required")
    if row.source_eid is not None and (not isinstance(row.source_eid, str) or not row.source_eid.strip()):
        raise ValueError("source_eid must be a nonempty string")
    json.dumps(row.value, allow_nan=False)
    if type(row.valid_from) is not dt.date or (
        row.valid_to is not None and (type(row.valid_to) is not dt.date or row.valid_to <= row.valid_from)
    ):
        raise ValueError("invalid half-open effective interval")
    contract.validate(row)
    text_parts = list(_strings(row.value))
    if not contract.numeric_key:
        text_parts.append(row.key)
    if any(has_pii(text) for text in text_parts):
        raise ValueError("personal data must not enter the public reference store")
    if contract.requires_source and not row.source_eid:
        raise ValueError("law-derived reference requires source_eid")
    if row.source_eid:
        if not session.scalar(sa.select(Unit.id).where(Unit.eid == row.source_eid)):
            raise ValueError("unknown source_eid")
        if contract.requires_source and not _source_applies(session, row.source_eid, row.valid_from):
            raise ValueError("source law is not applicable at valid_from")


def upsert_reference(session: Session, dataset: str, rows: list[RefRow], *, version: str = "v1",
                     pii_check: bool = True, reviewed_change: bool = False) -> RefOutcome:
    """Publish immutable rows. pii_check remains accepted but cannot disable string PII checks.

    Numeric values are validated as numbers and never mistaken for phone/ID strings.
    Repeating identical data is idempotent; edits require a new dataset version.
    An overlapping publication that changes existing data additionally requires explicit
    trusted curator review (reviewed_change); a version string alone is not approval.
    """
    contract = _CONTRACTS.get(dataset)
    if contract is None:
        raise ValueError(f"dataset has no registered contract: {dataset}")
    if not isinstance(version, str) or not version.strip() or len(version) > 128:
        raise ValueError("nonempty dataset version required")
    # Serialize publications across ALL versions of a logical key. Acquire in a
    # stable order so multi-key concurrent batches do not deadlock one another.
    for key in sorted({str(row.key) for row in rows}):
        lock = int.from_bytes(hashlib.sha256(f"{dataset}\0{key}".encode()).digest()[:8],
                              byteorder="big", signed=True)
        session.execute(sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
    out = RefOutcome()
    for row in rows:
        try:
            _validate(session, contract, row)
            existing = session.scalar(sa.select(ReferenceValue).where(
                ReferenceValue.dataset == dataset, ReferenceValue.key == row.key,
                ReferenceValue.valid_from == row.valid_from, ReferenceValue.version == version))
            if existing is not None:
                if (existing.value, existing.valid_to, existing.source_eid) != (
                    row.value, row.valid_to, row.source_eid
                ):
                    raise ValueError("published version is immutable; publish a new version")
            else:
                overlaps = session.scalars(sa.select(ReferenceValue).where(
                    ReferenceValue.dataset == dataset, ReferenceValue.key == row.key,
                    sa.or_(ReferenceValue.valid_to.is_(None), row.valid_from < ReferenceValue.valid_to),
                    *([ReferenceValue.valid_from < row.valid_to] if row.valid_to else [])
                )).all()
                if any(previous.version == version for previous in overlaps):
                    raise ValueError("overlapping rows in one published version")
                if not reviewed_change and any(
                    (previous.value, previous.source_eid) != (row.value, row.source_eid)
                    for previous in overlaps
                ):
                    raise ValueError("changed overlapping publication requires curator review")
                inserted = session.scalar(pg_insert(ReferenceValue).values(
                    dataset=dataset, key=row.key, value=row.value, valid_from=row.valid_from,
                    valid_to=row.valid_to, source_eid=row.source_eid, version=version
                ).on_conflict_do_nothing(constraint="uq_refval").returning(ReferenceValue.id))
                if inserted is None:
                    # Defend against a writer bypassing this adapter/lock convention.
                    stored = session.scalar(sa.select(ReferenceValue).where(
                        ReferenceValue.dataset == dataset, ReferenceValue.key == row.key,
                        ReferenceValue.valid_from == row.valid_from, ReferenceValue.version == version
                    ).execution_options(populate_existing=True))
                    if stored is None or (stored.value, stored.valid_to, stored.source_eid) != (
                        row.value, row.valid_to, row.source_eid
                    ):
                        raise ValueError("concurrent publication conflicts with immutable version")
            out.loaded += 1
        except (ValueError, TypeError) as exc:
            out.quarantined.append(row.key)
            out.reasons[str(row.key)] = str(exc)
    session.flush()
    return out


def lookup_reference(session: Session, dataset: str, key: str, as_of: dt.date, *,
                     version: str | None = None) -> ReferenceValue | None:
    """Last published applicable value, or an explicitly pinned version; recheck law@T."""
    contract = _CONTRACTS.get(dataset)
    if contract is None:
        raise ValueError(f"dataset has no registered contract: {dataset}")
    query = sa.select(ReferenceValue).where(
        ReferenceValue.dataset == dataset, ReferenceValue.key == key,
        ReferenceValue.valid_from <= as_of,
        sa.or_(ReferenceValue.valid_to.is_(None), as_of < ReferenceValue.valid_to))
    if version is not None:
        query = query.where(ReferenceValue.version == version)
    result = session.scalar(query.order_by(ReferenceValue.id.desc()).limit(1))
    if result is not None:
        try:
            _validate(session, contract, RefRow(result.key, result.value, result.valid_from,
                                               result.valid_to, result.source_eid))
        except (ValueError, TypeError):
            return None
        if contract.requires_source and not _source_applies(session, result.source_eid, as_of):
            return None
    return result
