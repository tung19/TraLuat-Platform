"""Stage 6 — handoff W1 → W2: nạp cây ParsedUnit vào Document/Unit/UnitVersion.

W2 sở hữu bitemporal; W1 chỉ cung cấp bản gốc. valid_from = date_effective của
văn bản (phased-commencement cấp Điều: dùng unit.effective_date khi có — thêm sau).
"""

from __future__ import annotations

import datetime as dt

from ..w2.models import Document, Unit, UnitVersion
from .structure import ParsedUnit, parse_structure


def build_ingest(text: str, doc_slug: str) -> list[ParsedUnit]:
    """Parse văn bản → cây ParsedUnit (stage 3)."""
    return parse_structure(text, doc_slug)


def load_to_w2(
    session,
    *,
    frbr_uri: str,
    doc_type: str,
    date_effective: dt.date,
    units: list[ParsedUnit],
    doc_number: str | None = None,
    lang: str = "vi",
) -> Document:
    """Ghi Document + Unit (cây) + UnitVersion (bản gốc, valid_from=date_effective)."""
    doc = Document(
        frbr_uri=frbr_uri, doc_number=doc_number, doc_type=doc_type,
        date_effective=date_effective, status="con_hieu_luc",
    )
    session.add(doc)
    session.flush()

    eid_to_id: dict[str, int] = {}
    for u in units:  # thứ tự tài liệu → cha trước con
        parent_id = eid_to_id.get(u.parent_eid) if u.parent_eid else None
        unit = Unit(
            document_id=doc.id, parent_id=parent_id, unit_type=u.unit_type,
            ordinal=u.ordinal, label=u.label, eid=u.eid,
        )
        session.add(unit)
        session.flush()
        eid_to_id[u.eid] = unit.id
        if u.text:  # chỉ đơn vị NỘI DUNG có version (kết cấu → không)
            session.add(UnitVersion(
                unit_id=unit.id, lang=lang, valid_from=date_effective, valid_to=None,
                text=u.text, status="con_hieu_luc",
            ))
    session.flush()
    return doc
