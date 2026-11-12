"""Synthetic legal fixtures through the real provider, index, transport and grounding."""
import datetime as dt
import json
import uuid

import httpx
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
from traluat.w3.local_gateway import LocalLLMGateway
from traluat.w3.retrieval import IndexedRetriever, retrieve_indexed
from traluat.w5.asgi import build_runtime_app

TEXT = "Doanh nghiệp phải nộp hồ sơ trong thời hạn 15 ngày làm việc."
CLAIM = "Doanh nghiệp cần nộp hồ sơ trong vòng 15 ngày làm việc."
D = dt.date(2024, 1, 1)


class SemanticFixture:
    dim = 1024
    model_id = "synthetic-semantic-v1"
    def embed(self, texts):
        return [[1.0] + [0.0] * 1023 for _ in texts]


class EvidenceJudge:
    def __init__(self):
        self.calls = []
    def supports(self, claim, source):
        self.calls.append((claim, source))
        return "promote" if claim == CLAIM and source == TEXT else "hold"


@pytest.fixture()
def knowledge(runtime):
    slug = "wire_" + uuid.uuid4().hex
    uri = f"synthetic:{slug}"
    eid = f"{slug}__dieu_1"
    with Session(runtime["admin"]) as s, s.begin():
        doc = load_to_w2(s, frbr_uri=uri, doc_type="nghi_dinh", date_effective=dt.date(2020, 1, 1),
                         units=build_ingest("Điều 1. " + TEXT, slug))
        did = doc.id
        reindex_document(s, uri, embedder=SemanticFixture())
    try:
        yield uri, eid
    finally:
        with Session(runtime["admin"]) as s, s.begin():
            units = sa.select(Unit.id).where(Unit.document_id == did)
            s.execute(sa.delete(Chunk).where(Chunk.unit_id.in_(units)))
            s.execute(sa.delete(UnitVersion).where(UnitVersion.unit_id.in_(units)))
            s.execute(sa.delete(Unit).where(Unit.document_id == did))
            s.execute(sa.delete(Document).where(Document.id == did))


def test_http_lookup_uses_indexed_semantics_local_llm_nli_and_sources(runtime, knowledge):
    uri, eid = knowledge
    sent = []
    def handler(request):
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"model_info": {"x": 1}})
        body = json.loads(request.content)
        sent.append(body)
        assert TEXT in body["messages"][1]["content"]
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"text": CLAIM, "citations": [
                {"unit_eid": eid, "claim": CLAIM, "quote": TEXT}]})}}]})
    judge = EvidenceJudge()
    local = LocalLLMGateway(base_url="http://127.0.0.1:11434/v1", model="synthetic-model",
                            transport=httpx.MockTransport(handler))
    app = build_runtime_app(jwt_secret=SECRET, session_factory=runtime["sessions"],
                            local_gateway=local, nli=judge,
                            retriever=IndexedRetriever(SemanticFixture()))
    with TestClient(app) as client:
        # No token overlap; only dense retrieval can find the synthetic statement.
        response = client.post("/lookup", json={"query": "submission deadline?", "as_of": str(D),
                                                "scope_frbr_uris": [uri]}, headers=runtime["headers"])
        assert response.status_code == 200
        body = response.json()
        assert body["answered"] and body["text"] == CLAIM and not body["is_demo"]
        assert body["sources"][0]["text"] == TEXT and body["sources"][0]["frbr_uri"] == uri
        assert body["route"]["destination"] == "local" and judge.calls
        # Explicit empty scope means no documents, not all documents.
        empty = client.post("/lookup", json={"query": "submission deadline?", "as_of": str(D),
                                             "scope_frbr_uris": []}, headers=runtime["headers"])
        assert empty.json()["abstain"] and len(sent) == 1
        status = client.get("/ai/status", headers=runtime["headers"]).json()
        assert status["semantic_search"] and status["nli_enabled"] and status["local_available"]


def test_stale_index_never_supplies_outdated_law(runtime, knowledge):
    uri, eid = knowledge
    with Session(runtime["admin"]) as s, s.begin():
        repo.apply_amendment(s, eid, "Doanh nghiệp phải nộp hồ sơ trong thời hạn 30 ngày làm việc.",
                             dt.date(2023, 1, 1))
        assert not retrieve_indexed(s, "submission deadline?", D,
                                    embedder=SemanticFixture(), scope_frbr_uris=[uri])
        reindex_document(s, uri, embedder=SemanticFixture())
        results = retrieve_indexed(s, "submission deadline?", D,
                                    embedder=SemanticFixture(), scope_frbr_uris=[uri])
        assert len(results) == 1 and "30 ngày" in results[0].chunk.span_text


def test_different_embedding_identity_not_mixed(runtime, knowledge):
    uri, _ = knowledge
    other = SemanticFixture()
    other.model_id = "another-model"
    with Session(runtime["admin"]) as s:
        assert not retrieve_indexed(s, "submission deadline?", D,
                                    embedder=other, scope_frbr_uris=[uri])


def test_invalid_vectors_do_not_destroy_existing_index(runtime, knowledge):
    uri, _ = knowledge
    class Broken(SemanticFixture):
        def embed(self, texts):
            return []
    with Session(runtime["admin"]) as s, s.begin():
        with pytest.raises(ValueError):
            reindex_document(s, uri, embedder=Broken())
        assert retrieve_indexed(s, "submission deadline?", D,
                                embedder=SemanticFixture(), scope_frbr_uris=[uri])


def test_local_failure_becomes_abstention_with_durable_failed_audit(runtime, knowledge):
    uri, _ = knowledge
    def handler(request):
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"model_info": {"x": 1}})
        return httpx.Response(503, text="private provider diagnostics")
    local = LocalLLMGateway(base_url="http://127.0.0.1:11434/v1", model="synthetic-model",
                            transport=httpx.MockTransport(handler))
    class NoCloud:
        def generate(self, *args, **kwargs):
            pytest.fail("client data must not fail over to a cloud gateway")
    app = build_runtime_app(jwt_secret=SECRET, session_factory=runtime["sessions"],
                            local_gateway=local, claude_gateway=NoCloud(),
                            retriever=IndexedRetriever(SemanticFixture()))
    with TestClient(app) as client:
        r = client.post("/lookup", json={"query": "q", "as_of": str(D),
                                         "scope_frbr_uris": [uri]}, headers=runtime["headers"])
    assert r.status_code == 200 and r.json()["reason"] == "local_model_unavailable"
    assert r.json()["text"] == "" and r.json()["abstain"]
    from traluat.w5.models import AuditLogRow
    with Session(runtime["admin"]) as s:
        phases = list(s.scalars(sa.select(AuditLogRow.phase).where(
            AuditLogRow.tenant_id == runtime["a"]).order_by(AuditLogRow.id)))
        assert phases == ["intent", "failed"]
