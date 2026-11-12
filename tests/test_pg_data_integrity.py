"""Adversarial W1/W2 integrity tests; all writes roll back in the test database."""

import datetime as dt
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import Session

from traluat.w1 import (
    InMemorySource,
    RawDocument,
    build_ingest,
    ingest_document,
    ingest_source,
    load_to_w2,
)
from traluat.w1.ingest import load_relations_to_w2
from traluat.w1.relations import RelationCandidate
from traluat.w2 import repo
from traluat.w2.db import make_engine
from traluat.w2.models import Document, NormRelation, Unit, UnitVersion

D = dt.date
AS_OF = D(2025, 1, 1)


def test_migration_rejects_legacy_duplicates_without_discarding_evidence(session):
    doc = seed(session)
    session.execute(sa.text("ALTER TABLE norm_relation DROP CONSTRAINT nr_dedupe"))
    session.execute(sa.text("ALTER TABLE norm_relation ADD CONSTRAINT nr_dedupe UNIQUE "
                            "(src_doc_id, src_unit_id, dst_doc_id, dst_unit_id, "
                            "relation_type, effective_date)"))
    for status, evidence in (("approved", "expert A"), ("rejected", "expert B")):
        session.add(NormRelation(src_doc_id=doc.id, dst_doc_id=doc.id,
                                 relation_type="amends", review_status=status,
                                 evidence_span=evidence))
    session.flush()
    query = sa.select(NormRelation.id, NormRelation.review_status,
                      NormRelation.evidence_span).where(NormRelation.src_doc_id == doc.id)
    before = session.execute(query.order_by(NormRelation.id)).all()
    path = Path(__file__).parents[1] / "alembic/versions/0004_data_integrity.py"
    spec = importlib.util.spec_from_file_location("migration_data_integrity", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with (
        pytest.raises(sa.exc.ProgrammingError, match="no rows were discarded"),
        session.begin_nested(),
        Operations.context(MigrationContext.configure(session.connection())),
    ):
        migration.upgrade()
    assert session.execute(query.order_by(NormRelation.id)).all() == before


@pytest.fixture
def session():
    engine = make_engine()
    try:
        connection = engine.connect()
    except sa.exc.OperationalError:
        engine.dispose()
        pytest.skip("isolated test PostgreSQL unavailable")
    with connection:
        transaction = connection.begin()
        s = Session(connection)
        try:
            yield s
        finally:
            s.close()
            if transaction.is_active:
                transaction.rollback()
    engine.dispose()


def seed(s):
    return load_to_w2(
        s, frbr_uri="audit:test/data", doc_type="nghi_dinh", date_effective=D(2020, 1, 1),
        doc_number="123/2020/NĐ-CP",
        units=build_ingest("Điều 1. Nghĩa vụ\n1. Có giấy phép.\na) Có đủ vốn.\nĐiều 2. Khác.", "integrity"),
    )


def uid(s, eid):
    return s.scalar(sa.select(Unit.id).where(Unit.eid == eid))


def candidate(*, article=1, kind="repeals"):
    return RelationCandidate(kind, "123/2020/NĐ-CP", article, D(2024, 1, 1), 0.92,
                             "rule:test", "synthetic audit fixture")


def relation(s, doc, *, kind="repeals", target="integrity__dieu_1", status="approved"):
    row = NormRelation(src_doc_id=doc.id, dst_doc_id=doc.id,
                       dst_unit_id=uid(s, target) if target else None,
                       relation_type=kind, review_status=status, effective_date=D(2024, 1, 1))
    s.add(row)
    s.flush()
    return row


def test_database_split_and_same_date_fold_preserve_known_as_of(session):
    seed(session)
    for version in session.scalars(sa.select(UnitVersion)):
        version.tx_from = dt.datetime(2000, 1, 1, tzinfo=dt.UTC)
    session.flush()
    known_before = dt.datetime(2001, 1, 1, tzinfo=dt.UTC)
    repo.apply_amendment(session, "integrity__dieu_1", "B", D(2024, 1, 1), order_key=1)
    assert repo.reconstruct_as_of(session, "integrity__dieu_1", AS_OF, known_as_of=known_before) == "Nghĩa vụ"
    known_middle = session.scalar(sa.select(sa.func.clock_timestamp()))
    repo.apply_amendment(session, "integrity__dieu_1", "C", D(2024, 1, 1), order_key=2)
    assert repo.reconstruct_as_of(session, "integrity__dieu_1", AS_OF, known_as_of=known_middle) == "B"
    assert repo.reconstruct_as_of(session, "integrity__dieu_1", AS_OF) == "C"


def test_repeal_applies_to_subtree_all_languages_and_does_not_repeat_hooks(session):
    doc = seed(session)
    child = "integrity__dieu_1__khoan_1"
    session.add(UnitVersion(unit_id=uid(session, child), lang="en", valid_from=D(2020, 1, 1), text="Permit required."))
    session.flush()
    row = relation(session, doc)
    calls = []
    hook = lambda _s, rel: calls.append(rel.id)
    repo.register_post_materialize(hook)
    try:
        assert repo.materialize(session, row)
        assert repo.materialize(session, row)
    finally:
        repo._POST_MATERIALIZE_HOOKS.remove(hook)
    assert calls == [row.id]
    for eid in ["integrity__dieu_1", child, child + "__diem_a"]:
        assert repo.reconstruct_as_of(session, eid, AS_OF) is None
        assert repo.reconstruct_as_of(session, eid, D(2023, 1, 1)) is not None
    assert repo.reconstruct_as_of(session, child, AS_OF, "en") is None
    assert "Có giấy phép" not in repo.document_as_of(session, doc.frbr_uri, AS_OF)
    assert repo.reconstruct_as_of(session, "integrity__dieu_2", AS_OF) == "Khác."


def test_unresolved_article_never_becomes_a_document_level_relation(session):
    doc = seed(session)
    created, unresolved = load_relations_to_w2(session, src_frbr_uri=doc.frbr_uri,
                                              candidates=[candidate(article=999)])
    assert not created and len(unresolved) == 1
    assert repo.reconstruct_as_of(session, "integrity__dieu_2", AS_OF) == "Khác."


def test_whole_document_repeal_preserves_historical_headings(session):
    doc = load_to_w2(session, frbr_uri="audit:chapter", doc_type="nghi_dinh",
                     date_effective=D(2020, 1, 1),
                     units=build_ingest("Chương I\nĐiều 1. Nội dung", "chapter"))
    row = relation(session, doc, target=None)
    assert repo.materialize(session, row)
    assert "Chương I" in repo.document_as_of(session, doc.frbr_uri, D(2023, 1, 1))
    assert repo.document_as_of(session, doc.frbr_uri, AS_OF) == ""


def test_unsupported_amendment_is_not_materialized_and_remains_caveated(session):
    doc = seed(session)
    row = relation(session, doc, kind="amends")
    assert not repo.materialize(session, row)
    assert row.materialized_at is None
    assert repo.pending_destructive_relation(session, "integrity__dieu_1")
    assert repo.reconstruct_as_of(session, "integrity__dieu_1", AS_OF) == "Nghĩa vụ"


def test_rejected_high_confidence_safe_edge_cannot_be_materialized_or_traversed(session):
    doc = seed(session)
    row = relation(session, doc, kind="cites", target="integrity__dieu_2", status="rejected")
    row.src_unit_id = uid(session, "integrity__dieu_1")
    row.confidence = 1.0
    session.flush()
    assert not repo.materialize(session, row)
    assert repo.multihop(session, "integrity__dieu_1", ["cites"], as_of=AS_OF) == []
    assert repo.neighborhood(session, "integrity__dieu_1", AS_OF)["edges"] == []


def test_per_document_savepoints_preserve_success_after_database_error(session):
    source = InMemorySource([
        RawDocument("batch", "Điều 1. A", "audit:batch/1", "nghi_dinh", D(2020, 1, 1)),
        RawDocument("batch", "Điều 1. B", "audit:batch/2", "nghi_dinh", D(2020, 1, 1)),
        RawDocument("batch3", "Điều 1. C", "audit:batch/3", "nghi_dinh", D(2020, 1, 1)),
    ])
    outcome = ingest_source(session, source)
    assert outcome.loaded == ["audit:batch/1", "audit:batch/3"]
    assert len(outcome.failed) == 1
    assert session.is_active
    assert session.scalar(sa.select(Document.id).where(Document.frbr_uri == "audit:batch/2")) is None
    assert repo.reconstruct_as_of(session, "batch__dieu_1", AS_OF) == "A"
    assert repo.reconstruct_as_of(session, "batch3__dieu_1", AS_OF) == "C"


def test_circular_issuer_collision_and_changed_source_are_not_silently_ignored(session):
    documents = []
    for issuer in ["BTC", "BXD"]:
        text = (f"Số: 01/2024/TT-{issuer}\nĐiều 1. Nội dung {issuer}\n"
                "Thông tư này có hiệu lực kể từ ngày 01 tháng 01 năm 2025.")
        doc, _ = ingest_document(session, text, "tt" + issuer)
        documents.append(doc)
        replay, _ = ingest_document(session, text, "tt" + issuer)
        assert replay.id == doc.id
        with pytest.raises(ValueError, match="nguồn/định danh khác"):
            ingest_document(session, text + "\nNội dung đã bị thay đổi.", "tt" + issuer)
    assert documents[0].id != documents[1].id


def test_relation_replay_preserves_review_and_database_enforces_null_safe_identity(session):
    doc = seed(session)
    created, _ = load_relations_to_w2(session, src_frbr_uri=doc.frbr_uri, candidates=[candidate(kind="cites")])
    created[0].review_status = "rejected"
    session.flush()
    replay, _ = load_relations_to_w2(session, src_frbr_uri=doc.frbr_uri, candidates=[candidate(kind="cites")])
    assert replay == []
    assert created[0].review_status == "rejected"
    with pytest.raises(sa.exc.IntegrityError), session.begin_nested():
        session.add(NormRelation(
            src_doc_id=doc.id, dst_doc_id=doc.id, dst_unit_id=uid(session, "integrity__dieu_1"),
            relation_type="cites", effective_date=D(2024, 1, 1), review_status="approved",
        ))
        session.flush()


def test_amendment_replay_is_scoped_to_target_and_language(session):
    seed(session)
    session.add(UnitVersion(unit_id=uid(session, "integrity__dieu_1"), lang="en",
                            valid_from=D(2020, 1, 1), text="A"))
    session.flush()
    for eid, lang in [("integrity__dieu_1", "vi"), ("integrity__dieu_2", "vi"), ("integrity__dieu_1", "en")]:
        repo.apply_amendment(session, eid, "B", D(2024, 1, 1), source_relation_id="shared", lang=lang)
        assert repo.reconstruct_as_of(session, eid, AS_OF, lang) == "B"
