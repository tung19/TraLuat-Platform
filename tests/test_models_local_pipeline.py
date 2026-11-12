"""Opt-in end-to-end BGE + Ollama + NLI, using only committed synthetic fixtures.

RUN_LOCAL_AI_TESTS=1 TEST_DATABASE_URL=<isolated *_test DB> python -m pytest this_file
Never downloads a model or changes the development knowledge store.
"""
import datetime as dt
import os
import uuid

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_pg_w5_runtime_security import SECRET
from tests.test_pg_w5_runtime_security import runtime as runtime  # noqa: PLC0414 — pytest fixture export
from traluat.w1 import build_ingest, load_to_w2
from traluat.w2 import repo
from traluat.w2.models import Chunk, Document, Unit, UnitVersion
from traluat.w3.indexer import reindex_document
from traluat.w5.ai_runtime import load_runtime_ai
from traluat.w5.asgi import build_runtime_app

pytestmark = pytest.mark.skipif(os.environ.get("RUN_LOCAL_AI_TESTS") != "1",
                                reason="explicit local-model integration opt-in required")


def test_real_local_models_answer_from_the_correct_version(runtime):
    ai = load_runtime_ai({"TRALUAT_AI_MODE": "local", "TRALUAT_MODELS_OFFLINE": "1",
                          "TRALUAT_LOCAL_MODEL": os.environ.get("LOCAL_TEST_MODEL", "qwen2.5-coder:latest"),
                          "TRALUAT_MODEL_DEVICE": "cpu"})
    assert ai.gateway.healthy(), "start the configured local model server first"
    slug = "live_synthetic_" + uuid.uuid4().hex
    uri, eid = f"synthetic:{slug}", f"{slug}__dieu_1"
    text = "Doanh nghiệp phải nộp hồ sơ trong thời hạn 15 ngày làm việc."
    with Session(runtime["admin"]) as s, s.begin():
        doc = load_to_w2(s, frbr_uri=uri, doc_type="nghi_dinh", date_effective=dt.date(2020, 1, 1),
                         units=build_ingest("Điều 1. " + text, slug))
        did = doc.id
        repo.apply_amendment(s, eid, text.replace("15", "30"), dt.date(2023, 1, 1))
        reindex_document(s, uri, embedder=ai.retriever.embedder)
    try:
        app = build_runtime_app(jwt_secret=SECRET, session_factory=runtime["sessions"],
                                local_gateway=ai.gateway, retriever=ai.retriever, nli=ai.nli)
        with TestClient(app) as client:
            for as_of, days in (("2022-01-01", "15"), ("2024-01-01", "30")):
                response = client.post("/lookup", json={
                    "query": "Thời hạn nộp hồ sơ của doanh nghiệp là bao lâu?",
                    "as_of": as_of, "scope_frbr_uris": [uri]}, headers=runtime["headers"])
                body = response.json()
                assert response.status_code == 200 and body["answered"], body
                assert days in body["text"] and body["citations"] == [eid]
                assert body["sources"][0]["text"] == text.replace("15", days)
                assert body["model"] == ai.gateway.model and not body["is_demo"]
                print(f"local model {body['model']} at {as_of}: {body['text']}")
            response = client.post("/lookup", json={"query": "Thủ đô nước Pháp là gì?",
                                   "as_of": "2024-01-01", "scope_frbr_uris": [uri]},
                                   headers=runtime["headers"])
            assert response.json()["abstain"] and response.json()["text"] == ""
    finally:
        with Session(runtime["admin"]) as s, s.begin():
            units = sa.select(Unit.id).where(Unit.document_id == did)
            s.execute(sa.delete(Chunk).where(Chunk.unit_id.in_(units)))
            s.execute(sa.delete(UnitVersion).where(UnitVersion.unit_id.in_(units)))
            s.execute(sa.delete(Unit).where(Unit.document_id == did))
            s.execute(sa.delete(Document).where(Document.id == did))
