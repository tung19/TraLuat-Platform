"""Audit-only, synthetic inputs; uses an isolated database and rolls back."""
import datetime as dt
import json
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from traluat.tools.calculators import run
from traluat.tools.reference import RefRow, lookup_reference, upsert_reference
from traluat.tools.templates import add_template

engine = create_engine("postgresql+psycopg://audit:audit-local-only@127.0.0.1:55433/traluat_test")
tag = uuid.uuid4().hex
with engine.connect() as connection:
    transaction = connection.begin()
    with Session(bind=connection) as session:
        upsert_reference(session, "thue_gtgt", [RefRow(
            tag, {"rate": -0.1}, dt.date(2020, 1, 1),
            source_eid="NONEXISTENT-SYNTHETIC-SOURCE")], pii_check=False)
        result = run(session, "thue_gtgt", {"gia": 100, "loai": tag}, dt.date(2022, 1, 1))
        print("reference_without_integrity_gate", json.dumps({
            "tax": result.value, "source_eid": result.source_eid}))
        assert result.value["thue"] == -10

        dataset = "audit_version_" + tag
        for version, number in [("v1", 100), ("v2", 200)]:
            upsert_reference(session, dataset, [RefRow(
                "key", {"amount": number}, dt.date(2020, 1, 1))], version=version)
        selected = lookup_reference(session, dataset, "key", dt.date(2022, 1, 1))
        print("reference_version_collision", json.dumps({
            "selected_version": selected.version, "selected_value": selected.value,
            "new_version": "v2", "new_value": 200}))

        row = add_template(session, "audit_" + tag, "synthetic audit template",
                           "Email: synthetic@example.invalid; CCCD: 123456789012")
        print("public_template_accepts_pii", json.dumps({
            "inserted": row.id is not None, "body": row.body}))
    transaction.rollback()
engine.dispose()
