"""Synthetic law anchors for reference adapter tests; these are not legal seed data."""
import datetime as dt

import sqlalchemy as sa

from traluat.w2.models import Document, Unit, UnitVersion


def seed_reference_sources(session, eids):
    doc = session.scalar(sa.select(Document).where(Document.frbr_uri == 'trl:test/reference-fixtures'))
    if doc is None:
        doc = Document(frbr_uri='trl:test/reference-fixtures', doc_type='luat',
                       date_effective=dt.date(1900, 1, 1), status='con_hieu_luc')
        session.add(doc)
        session.flush()
    for index, eid in enumerate(eids):
        if session.scalar(sa.select(Unit.id).where(Unit.eid == eid)):
            continue
        unit = Unit(document_id=doc.id, unit_type='article', ordinal=index + 1,
                    label='Synthetic test article', eid=eid)
        session.add(unit)
        session.flush()
        session.add(UnitVersion(unit_id=unit.id, lang='vi', valid_from=dt.date(1900, 1, 1),
                                text='Synthetic source fixture; no real legal rule asserted.',
                                status='con_hieu_luc'))
    session.flush()
