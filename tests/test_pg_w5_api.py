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
from tests.test_w1_structure import SAMPLE


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


def test_directory_page(client):
    r = client.get("/directory")
    assert r.status_code == 200 and "leaflet" in r.text and "danh bạ" in r.text
    assert "/directory/nearby" in r.text          # JS gọi endpoint KNN


def test_directory_nearby_endpoint(client):
    pytest.importorskip("geoalchemy2")
    from traluat.w1.directory import add_directory_entry

    # chèn 1 mục qua session của service (client fixture dùng chung session s)
    from traluat.w5.api import get_service
    gen = client.app.dependency_overrides[get_service]()
    svc = next(gen)
    add_directory_entry(svc.s, "toa_an", "TAND TP.HCM (api)",
                        lat=10.7769, lon=106.7009, province="HCM")
    r = client.get("/directory/nearby?lat=10.7769&lon=106.7009&radius_m=50000",
                   headers={"Authorization": f"Bearer {_tok(tenant_id='t1', role='viewer')}"})
    assert r.status_code == 200
    hit = next(x for x in r.json() if x["name"] == "TAND TP.HCM (api)")
    assert abs(hit["lat"] - 10.7769) < 1e-4 and abs(hit["lon"] - 106.7009) < 1e-4


def test_alerts_subscribe_and_list(client):
    import uuid
    tid = str(uuid.uuid4())
    hdr = {"Authorization": f"Bearer {_tok(tenant_id=tid, role='lawyer')}"}
    sub = client.post("/alerts/subscribe", json={"frbr": FRBR}, headers=hdr)
    assert sub.status_code == 200 and sub.json()["subscribed"] == FRBR
    lst = client.get("/alerts", headers=hdr)
    assert lst.status_code == 200 and isinstance(lst.json(), list)   # hộp thư (rỗng tới khi có đổi)


def test_alerts_subscribe_viewer_forbidden(client):
    import uuid
    hdr = {"Authorization": f"Bearer {_tok(tenant_id=str(uuid.uuid4()), role='viewer')}"}
    assert client.post("/alerts/subscribe", json={"frbr": FRBR}, headers=hdr).status_code == 403


def _viewer():
    return {"Authorization": f"Bearer {_tok(tenant_id='t1', role='viewer')}"}


def test_tools_page(client):
    r = client.get("/tools")
    assert r.status_code == 200
    for frag in ("/lookup", "/compare", "/draft", "/deadline"):   # 4 form gọi đúng endpoint
        assert frag in r.text


def test_deadline_endpoint(client):
    import datetime as _dt

    from traluat.w1.reference import RefRow, upsert_reference
    from traluat.w5.api import get_service
    svc = next(client.app.dependency_overrides[get_service]())
    upsert_reference(svc.s, "thoi_hieu", [
        RefRow("khang_cao_so_tham_ds", {"value": 15, "unit": "day"},
               _dt.date(2016, 7, 1), None, "bltts2015__dieu_273")], pii_check=False)
    r = client.get("/deadline?kind=khang_cao_so_tham_ds&start=2022-03-04&as_of=2022-06-01",
                   headers=_viewer())
    assert r.status_code == 200
    d = r.json()
    assert d["deadline"] == "2022-03-21"              # +15 lùi T7→T2
    assert d["rolled_from"] == "2022-03-19" and d["source_eid"] == "bltts2015__dieu_273"


def test_bad_date_returns_422_not_500(client):
    # F4: ngày sai định dạng là lỗi CLIENT → 422, không phải 500
    assert client.get("/compare?frbr=trl:vn/nd/99/2020&a=2022-13-99&b=2022-06-01",
                      headers=_viewer()).status_code == 422
    assert client.get("/deadline?kind=x&start=hom-nay&as_of=2022-01-01",
                      headers=_viewer()).status_code == 422
    assert client.post("/lookup", json={"query": "x", "as_of": ""},
                       headers=_viewer()).status_code == 422   # thiếu ngày bắt buộc
    assert client.post("/analyze", json={"facts": "x", "as_of": "2022/01/01"},
                       headers=_lawyer()).status_code == 422


def test_optional_date_omitted_still_ok(client):
    # as_of tuỳ chọn bỏ trống → mặc định (today/None), KHÔNG 422
    r = client.get("/doc?frbr=trl:vn/nd/99/2020", headers=_lawyer())
    assert r.status_code == 200


def test_deadline_no_data_404(client):
    r = client.get("/deadline?kind=khong-co&start=2022-01-01&as_of=2022-01-01",
                   headers=_viewer())
    assert r.status_code == 404


def test_lookup_endpoint(client):
    r = client.post("/lookup", json={"query": "vốn pháp định", "as_of": "2022-01-01"},
                    headers=_viewer())                     # KB công → viewer OK
    assert r.status_code == 200
    d = r.json()
    assert "abstain" in d and d["ai_label"] and d["trace_id"]


def test_compare_endpoint(client):
    r = client.get("/compare?frbr=trl:vn/nd/99/2020&a=2021-06-01&b=2022-06-01",
                   headers=_viewer())
    assert r.status_code == 200
    d = r.json()
    assert d["frbr"] == "trl:vn/nd/99/2020" and isinstance(d["changes"], list)


def test_compare_missing_doc_404(client):
    r = client.get("/compare?frbr=trl:vn/nd/khong-co&a=2021-01-01&b=2022-01-01",
                   headers=_viewer())
    assert r.status_code == 404


def test_draft_endpoint_abstain_no_template(client):
    # chưa seed template → grounded-draft abstain 'no_template' (chứng minh wiring+gate)
    r = client.post("/draft", json={"kind": "khoi_kien", "facts": "tranh chấp hợp đồng",
                                     "as_of": "2022-01-01"}, headers=_lawyer())
    assert r.status_code == 200
    d = r.json()
    assert d["abstain"] is True and d["ai_label"] and d.get("route") in ("local", None)


def test_draft_viewer_forbidden(client):
    r = client.post("/draft", json={"kind": "x", "facts": "y", "as_of": "2022-01-01"},
                    headers=_viewer())
    assert r.status_code == 403


def _client_shared_audit():
    """Client với MỘT LegalService (audit dùng chung) → test kiểm được audit trail."""
    from traluat.w5.audit import AuditLog
    conn = make_engine().connect()
    trans = conn.begin()
    s = Session(bind=conn, future=True)
    load_to_w2(s, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
               units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP")
    audit = AuditLog()
    svc = LegalService(s, local_gateway=EchoLLMGateway(), claude_gateway=EchoLLMGateway(),
                       audit=audit)

    def provider():
        yield svc                                       # cùng 1 service → audit dùng chung

    app = create_app(jwt_secret=SECRET, service_provider=provider)
    return TestClient(app), audit, (s, trans, conn)


def test_judgment_writes_audit_trail():
    # CN-03 high-risk: judgment PHẢI để lại bằng chứng audit (intent + done)
    try:
        tc, audit, (s, trans, conn) = _client_shared_audit()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    try:
        r = tc.post("/judgment", json={"cited_eids": [], "expected_governing": ["x"],
                                       "as_of": "2022-01-01"}, headers=_lawyer())
        tid = r.json()["trace_id"]
        phases = [e.phase for e in audit.by_trace(tid)]
        assert "intent" in phases and "done" in phases      # write-ahead + confirm
        assert audit.by_trace(tid)[0].action == "judgment"
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def test_draft_writes_audit_trail():
    try:
        tc, audit, (s, trans, conn) = _client_shared_audit()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    try:
        r = tc.post("/draft", json={"kind": "khoi_kien", "facts": "x", "as_of": "2022-01-01"},
                    headers=_lawyer())
        tid = r.json()["trace_id"]
        e = audit.by_trace(tid)
        assert e and e[0].action == "draft" and e[0].data_class == "client-sensitive"
        assert e[0].llm_destination == "local"              # tình tiết khách không rời VN
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def test_judgment_endpoint_flags_missing_binding(client):
    # điều còn hiệu lực @ngày xử mà bản án không viện → cờ (second-opinion)
    r = client.post("/judgment", json={"cited_eids": [],
                                       "expected_governing": ["nd99__dieu_1"],
                                       "as_of": "2022-01-01"}, headers=_lawyer())
    assert r.status_code == 200
    d = r.json()
    assert d["flagged"] is True and "nd99__dieu_1" in d["missing_binding"]
    assert d["hitl_required"] is True                       # CN-03 high-risk


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
