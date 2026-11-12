"""Synthetic W1/W2 audit reproductions, 2026-11-10.

Run from repository root with PYTHONPATH=src and its virtualenv Python.
Requires the disposable audit PostgreSQL schema to have been migrated already.
Does not invoke pytest, conftest, migrations, database creation, or commits.
All PostgreSQL writes are enclosed in transactions and rolled back.

The URL is intentionally restricted to the disposable audit account/database on
127.0.0.1:55433. This script must never target a developer/production database.
"""

from __future__ import annotations

import datetime as dt
import os
import warnings
from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from traluat.w1.ingest import (
    build_ingest,
    derive_frbr_uri,
    ingest_document,
    load_relations_to_w2,
    load_to_w2,
)
from traluat.w1.metadata import DocMeta, extract_effective_overrides, extract_metadata
from traluat.w1.relations import RelationCandidate
from traluat.w1.source import InMemorySource, RawDocument, ingest_source
from traluat.w1.structure import parse_structure
from traluat.w2 import repo
from traluat.w2.bitemporal import (
    UnitVersion as PureVersion,
    apply_amendment as pure_amend,
    reconstruct_as_of as pure_reconstruct,
)
from traluat.w2.db import make_engine
from traluat.w2.models import NormRelation, Unit, UnitVersion

D = dt.date


def timestamp(year):
    return dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)


def pure_cases():
    versions = [PureVersion("e", "vi", D(2020, 1, 1), None, "A", tx_from=timestamp(2020))]
    print("PURE_TX before=", pure_reconstruct(versions, "e", D(2025, 1, 1), known_as_of=timestamp(2022)))
    pure_amend(versions, "e", "B", D(2024, 1, 1), now=timestamp(2023))
    print("PURE_TX after=", pure_reconstruct(versions, "e", D(2025, 1, 1), known_as_of=timestamp(2022)))

    for number in ["01/2024/TT-BTC", "01/2024/TT-BXD"]:
        print("PURE_FRBR", number, derive_frbr_uri(DocMeta(doc_number=number, doc_type="thong_tu")))

    text = "Chương I\nMục 1\nĐiều 1. A\nMục 2\nĐiều 2. B\nChương II\nMục 1\nĐiều 3. C"
    for unit in parse_structure(text, "doc"):
        print("STRUCTURE", unit)

    text = "Điều 1. Các nghĩa vụ\n1. Thực hiện các việc:\na) Có giấy phép và\nđáp ứng điều kiện vốn.\nb) Báo cáo."
    for unit in parse_structure(text, "x"):
        print("CONTINUATION", unit.eid, repr(unit.text))

    text = (
        "Số: 99/2020/NĐ-CP\n"
        "Khoản 1 Điều 2 có hiệu lực kể từ ngày 01 tháng 01 năm 2022.\n"
        "Nghị định này có hiệu lực kể từ ngày 01 tháng 01 năm 2021."
    )
    print("METADATA", extract_metadata(text))
    print("OVERRIDES", extract_effective_overrides(text, "x"))


def isolated_engine():
    value = os.environ.get(
        "TRALUAT_AUDIT_DATABASE_URL",
        "postgresql+psycopg://audit:audit-local-only@127.0.0.1:55433/traluat_test",
    )
    url = make_url(value)
    if not (
        url.drivername == "postgresql+psycopg"
        and url.host == "127.0.0.1"
        and url.port == 55433
        and url.username == "audit"
        and url.database == "traluat_test"
    ):
        raise SystemExit("Refusing URL outside the disposable local audit database")
    return make_engine(value)


@contextmanager
def rollback_session(engine):
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(connection)
        try:
            yield session
        finally:
            session.close()
            if transaction.is_active:
                transaction.rollback()


def repeal_cases(engine):
    with rollback_session(engine) as session:
        target = load_to_w2(
            session, frbr_uri="audit:data/target", doc_type="nghi_dinh",
            date_effective=D(2020, 1, 1), doc_number="1/2020/NĐ-CP",
            units=build_ingest(
                "Điều 1. Các nghĩa vụ\n1. Phải có giấy phép.\na) Có đủ vốn.\nĐiều 2. Nghĩa vụ khác",
                "auditdata",
            ),
        )
        uid = session.scalar(sa.select(Unit.id).where(Unit.eid == "auditdata__dieu_1"))
        relation = NormRelation(
            src_doc_id=target.id, dst_doc_id=target.id, dst_unit_id=uid,
            relation_type="repeals", effective_date=D(2024, 1, 1), review_status="approved",
        )
        session.add(relation)
        session.flush()
        repo.materialize(session, relation)
        print(
            "PARENT_REPEAL parent=", repo.effect_status(session, "auditdata__dieu_1", D(2025, 1, 1)).value,
            "child=", repo.effect_status(session, "auditdata__dieu_1__khoan_1", D(2025, 1, 1)).value,
        )
        print("PARENT_REPEAL doc=", repr(repo.document_as_of(session, "audit:data/target", D(2025, 1, 1))))

        candidate = RelationCandidate(
            "repeals", "1/2020/NĐ-CP", 999, D(2024, 2, 1),
            0.75, "rule:test", "Bãi bỏ Điều 999",
        )
        created, unresolved = load_relations_to_w2(
            session, src_frbr_uri="audit:data/target", candidates=[candidate],
        )
        wrong = created[0]
        print("MISSING_TARGET unresolved_count=", len(unresolved), "dst_unit_id=", wrong.dst_unit_id)
        wrong.review_status = "approved"
        repo.materialize(session, wrong)
        print("MISSING_TARGET unrelated_article2=", repo.effect_status(session, "auditdata__dieu_2", D(2025, 1, 1)).value)


def batch_case(engine):
    with rollback_session(engine) as session:
        documents = [
            RawDocument(
                doc_slug="auditbatch", text="Điều 1. A", frbr_uri="audit:batch/1",
                doc_type="nghi_dinh", date_effective=D(2020, 1, 1),
            ),
            RawDocument(
                doc_slug="auditbatch", text="Điều 1. B", frbr_uri="audit:batch/2",
                doc_type="nghi_dinh", date_effective=D(2020, 1, 1),
            ),
            RawDocument(
                doc_slug="auditbatch3", text="Điều 1. C", frbr_uri="audit:batch/3",
                doc_type="nghi_dinh", date_effective=D(2020, 1, 1),
            ),
        ]
        outcome = ingest_source(session, InMemorySource(documents))
        print(
            "BATCH loaded=", outcome.loaded,
            "failed=", [(slug, error.splitlines()[0]) for slug, error in outcome.failed],
            "session_active=", session.is_active,
        )


def temporal_and_replay_cases(engine):
    with rollback_session(engine) as session:
        document = load_to_w2(
            session, frbr_uri="audit:data2", doc_type="nghi_dinh",
            date_effective=D(2020, 1, 1), doc_number="1/2020/NĐ-CP",
            units=build_ingest("Điều 1. A\nĐiều 2. A2", "auditdata2"),
        )
        for row in session.scalars(sa.select(UnitVersion).join(Unit).where(Unit.document_id == document.id)):
            row.tx_from = timestamp(2020)
        session.flush()
        print("TX before=", repo.reconstruct_as_of(session, "auditdata2__dieu_1", D(2025, 1, 1), known_as_of=timestamp(2022)))
        repo.apply_amendment(session, "auditdata2__dieu_1", "B", D(2024, 1, 1), source_relation_id="audit:r")
        print("TX after=", repo.reconstruct_as_of(session, "auditdata2__dieu_1", D(2025, 1, 1), known_as_of=timestamp(2022)))

        repo.apply_amendment(session, "auditdata2__dieu_2", "B2", D(2024, 1, 1), source_relation_id="audit:r")
        print("IDEMPOTENT second unit text=", repo.reconstruct_as_of(session, "auditdata2__dieu_2", D(2025, 1, 1)))

        candidate = RelationCandidate("cites", "1/2020/NĐ-CP", 1, D(2024, 1, 1), 0.92, "rule:test", "cites")
        load_relations_to_w2(session, src_frbr_uri="audit:data2", candidates=[candidate])
        load_relations_to_w2(session, src_frbr_uri="audit:data2", candidates=[candidate])
        print("RELATIONS repeated rows=", session.scalar(sa.select(sa.func.count()).select_from(NormRelation).where(NormRelation.src_doc_id == document.id)))

        relation = NormRelation(
            src_doc_id=document.id, dst_doc_id=document.id, relation_type="amends",
            dst_unit_id=session.scalar(sa.select(Unit.id).where(Unit.eid == "auditdata2__dieu_2")),
            effective_date=D(2024, 1, 1), review_status="approved",
        )
        session.add(relation)
        session.flush()
        print("AMENDS result=", repo.materialize(session, relation), "text=", repo.reconstruct_as_of(session, "auditdata2__dieu_2", D(2025, 1, 1)))


def frbr_case(engine):
    with rollback_session(engine) as session:
        for index, suffix in enumerate(["BTC", "BXD"]):
            text = (
                f"Số: 01/2024/TT-{suffix}\n"
                "Thông tư này có hiệu lực kể từ ngày 01 tháng 01 năm 2025.\n"
                f"Điều 1. Nghĩa vụ {suffix}"
            )
            document, _ = ingest_document(session, text, "auditt" + str(index))
            print("FRBR suffix=", suffix, "doc_id=", document.id, "doc_number=", document.doc_number, "frbr=", document.frbr_uri)


if __name__ == "__main__":
    pure_cases()
    engine = isolated_engine()
    try:
        repeal_cases(engine)
        batch_case(engine)
        temporal_and_replay_cases(engine)
        frbr_case(engine)
    finally:
        engine.dispose()
