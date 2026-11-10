"""FR-04 Termbank — thuật ngữ VN-EN-ZH, NEO điều–khoản (alignment offline).

Trên reference-data-plane (dataset 'termbank'). Dùng để render EN/ZH + đối chiếu
song-ngữ. Suy luận 1 lần (legal-conclusion cache language-neutral), chỉ render lại.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from .reference import RefRow, lookup_reference, upsert_reference

_EPOCH = dt.date(2000, 1, 1)


def add_term(session: Session, vn: str, *, en: str | None = None, zh: str | None = None,
             definition: str | None = None, source_eid: str | None = None,
             valid_from: dt.date = _EPOCH) -> None:
    upsert_reference(session, "termbank", [RefRow(
        vn, {"vn": vn, "en": en, "zh": zh, "def": definition}, valid_from, None, source_eid)],
        pii_check=False)


def lookup_term(session: Session, vn: str, as_of: dt.date, lang: str = "en") -> str | None:
    rv = lookup_reference(session, "termbank", vn, as_of)
    return rv.value.get(lang) if rv else None
