"""End-to-end (Postgres + FastAPI): /analyze — JWT→tenant, RBAC, residency route."""

from __future__ import annotations

import datetime as dt

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.w2.db import make_engine
from traluat.w3 import EchoLLMGateway
from traluat.w5 import LegalService
from traluat.w5.api import create_app

D = dt.date
SECRET = "s3cret"
FRBR = "trl:vn/nd/99/2020"
from tests.test_w1_structure import SAMPLE  # noqa: E402


def _tok(**claims) -> str:
    return jwt.encode(claims, SECRET, algorithm="HS256")


class _DownEcho(EchoLLMGateway):
    """Mô phỏng vLLM local DOWN (health-probe B5)."""
    def healthy(self) -> bool:
        return False


def _make_client(local_gateway):
    conn = make_engine().connect()
    trans = conn.begin()
    s = Session(bind=conn, future=True)
    load_to_w2(s, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
               units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP")

    def provider():
        yield LegalService(s, local_gateway=local_gateway, claude_gateway=EchoLLMGateway())

    app = create_app(jwt_secret=SECRET, service_provider=provider)
    return TestClient(app), (s, trans, conn)


@pytest.fixture()
def client():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    s = Session(bind=conn, future=True)
    load_to_w2(s, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
               units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP")

    def provider():
        yield LegalService(s, local_gateway=EchoLLMGateway(), claude_gateway=EchoLLMGateway())

    app = create_app(jwt_secret=SECRET, service_provider=provider)
    try:
        yield TestClient(app)
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


BODY = {"facts": "vốn pháp định tối thiểu của doanh nghiệp", "as_of": "2022-01-01"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_index_and_metrics(client):
    idx = client.get("/")
    assert idx.status_code == 200 and "TraLuat" in idx.text   # W7 UI tối thiểu
    assert client.get("/metrics").status_code == 200           # observability scrape


def test_graph_view_page(client):
    r = client.get("/graph")
    assert r.status_code == 200 and "cytoscape" in r.text and "đồ thị" in r.text
    assert "PageRank" in r.text and "in-degree" in r.text   # overlay importance


def test_graph_central_empty_without_neo4j(client):
    # không cấu hình Neo4j → /graph/central trả {} (frontend fallback in-degree)
    r = client.get("/graph/central",
                   headers={"Authorization": f"Bearer {_tok(tenant_id='t1', role='viewer')}"})
    assert r.status_code == 200 and r.json() == {}


def _lawyer():
    return {"Authorization": f"Bearer {_tok(tenant_id='t1', role='lawyer')}"}


def test_doc_citation_nav(client):
    r = client.get("/doc?frbr=trl:vn/nd/99/2020&as_of=2022-01-01", headers=_lawyer())
    assert r.status_code == 200
    assert "Điều 3" in r.json()["text"]                 # văn bản tại ngày T


def test_review_endpoint(client):
    r = client.post("/review", json={"text": "Hợp đồng. Hai bên cam kết bảo mật thông tin."},
                    headers=_lawyer())
    assert r.status_code == 200
    f = {x["rule"]: x["status"] for x in r.json()}
    assert f["bảo mật"] == "present" and f["bất khả kháng"] == "missing"


def test_review_viewer_forbidden(client):
    r = client.post("/review", json={"text": "x"},
                    headers={"Authorization": f"Bearer {_tok(tenant_id='t1', role='viewer')}"})
    assert r.status_code == 403


def test_review_queue(client):
    r = client.get("/review/queue",
                   headers={"Authorization": f"Bearer {_tok(tenant_id='t1', role='reviewer')}"})
    assert r.status_code == 200 and isinstance(r.json(), list)   # HITL queue


def test_graph_endpoint(client):
    r = client.get("/graph/nd99__dieu_1",
                   headers={"Authorization": f"Bearer {_tok(tenant_id='t1', role='viewer')}"})
    assert r.status_code == 200
    d = r.json()
    assert d["center"] == "nd99__dieu_1"
    assert any(n["eid"] == "nd99__dieu_1" for n in d["nodes"])   # FR-37 graph data


def test_analyze_lawyer_ok(client):
    r = client.post("/analyze", json=BODY,
                    headers={"Authorization": f"Bearer {_tok(tenant_id='t1', role='lawyer')}"})
    assert r.status_code == 200
    d = r.json()
    assert d["answered"] and d["ai_label"] and d["trace_id"]
    assert d["route"]["destination"] == "local"       # dữ liệu khách → local
    assert "nd99__dieu_3__khoan_2" in d["parties"][0]["citations"]


def test_missing_token_401(client):
    assert client.post("/analyze", json=BODY).status_code == 401


def test_token_without_tenant_401(client):
    r = client.post("/analyze", json=BODY,
                    headers={"Authorization": f"Bearer {_tok(role='lawyer')}"})
    assert r.status_code == 401


def test_viewer_role_403(client):
    r = client.post("/analyze", json=BODY,
                    headers={"Authorization": f"Bearer {_tok(tenant_id='t1', role='viewer')}"})
    assert r.status_code == 403


def test_local_down_denies():
    # B5/R2: local gateway unhealthy (probe) → dữ liệu khách DENY, KHÔNG do client body
    try:
        tc, (s, trans, conn) = _make_client(_DownEcho())
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    try:
        r = tc.post("/analyze", json=BODY,
                    headers={"Authorization": f"Bearer {_tok(tenant_id='t1', role='lawyer')}"})
        d = r.json()
        assert not d["answered"] and d["route"]["destination"] == "deny"   # R2
        assert d["ai_label"] and d["trace_id"]
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()
