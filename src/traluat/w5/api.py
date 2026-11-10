"""FastAPI surface (L11) — expose LegalService. Infra-lift xương sống PAKTON.

Bất biến giữ ở đây: (1) mọi route cần JWT→TenantContext (không tenant → 401);
(2) RBAC require_role; (3) response luôn có nhãn AI + trace_id; (4) EgressPolicy +
audit nằm trong LegalService (route không bypass).

Celery/SSE/nginx cắm quanh app này sau. `service_provider` là dependency sinh
LegalService (bind session/tenant) — prod nối DB thật, test override bằng session kiểm.
"""

from __future__ import annotations

import datetime as dt

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from ..w4 import CaseInput
from .auth import decode_context
from .metrics import Metrics
from .service import LegalService
from .tenancy import MissingTenant, TenantContext, require_role

_INDEX_HTML = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>TraLuat</title></head><body style="font-family:sans-serif;max-width:720px;margin:2rem auto">
<h1>TraLuat — trợ lý pháp lý</h1>
<p>Nhập tình tiết + ngày sự kiện. Kết quả có <b>trích dẫn điều–khoản tại ngày T</b>,
hoặc <b>abstain</b> khi không đủ căn cứ. Mọi output gắn nhãn AI.</p>
<form id="f"><textarea id="facts" rows="4" style="width:100%" placeholder="tình tiết..."></textarea>
<input id="asof" value="2022-01-01"> <button>Phân tích</button></form>
<pre id="out"></pre>
<script>
f.onsubmit=async e=>{e.preventDefault();out.textContent='...';
 const r=await fetch('/analyze',{method:'POST',headers:{'Content-Type':'application/json',
  'Authorization':'Bearer '+(localStorage.tok||'')},
  body:JSON.stringify({facts:facts.value,as_of:asof.value})});
 out.textContent=JSON.stringify(await r.json(),null,2);};
</script></body></html>"""


class AnalyzeRequest(BaseModel):
    facts: str
    as_of: str                       # ISO date
    parties: list[str] | None = None
    # I3: tình tiết LUÔN client-sensitive (không có cờ client_data).
    # B5: local_available do service health-probe, không nhận từ client.


def get_service() -> LegalService:   # placeholder — create_app/ test override
    raise RuntimeError("get_service chưa cấu hình")


def create_app(*, jwt_secret: str, service_provider, metrics: Metrics | None = None) -> FastAPI:
    app = FastAPI(title="TraLuat API")
    app.dependency_overrides[get_service] = service_provider
    app.state.metrics = metrics or Metrics()

    def auth(authorization: str | None = Header(default=None)) -> TenantContext:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "missing bearer token")
        try:
            return decode_context(authorization[7:], jwt_secret)
        except MissingTenant:
            raise HTTPException(401, "token thiếu tenant_id")
        except jwt.PyJWTError:
            raise HTTPException(401, "token không hợp lệ")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index():                       # W7 Experience (tối thiểu) — form + nhãn AI
        return _INDEX_HTML

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics_ep():                  # observability — scrape Prometheus
        return app.state.metrics.render()

    @app.post("/analyze")
    def analyze(
        body: AnalyzeRequest,
        ctx: TenantContext = Depends(auth),
        svc: LegalService = Depends(get_service),
    ):
        try:
            require_role(ctx, "lawyer", "reviewer", "owner")
        except PermissionError as e:
            raise HTTPException(403, str(e))
        resp = svc.analyze(
            CaseInput(facts=body.facts, parties=body.parties or []),
            dt.date.fromisoformat(body.as_of), ctx,   # facts sensitive (I3); probe (B5)
        )
        return {
            "answered": resp.answered,
            "trace_id": resp.trace_id,
            "ai_label": resp.ai_label,            # bất biến (2)
            "reason": resp.reason,
            "route": {
                "data_class": resp.route.data_class.value,
                "destination": resp.route.destination.value,
                "reason": resp.route.reason,
            },
            "parties": [
                {"party": p.party, "abstain": p.abstain, "reason": p.reason,
                 "relief": p.relief, "citations": p.citations}
                for p in (resp.adjudication.parties if resp.adjudication else [])
            ],
        }

    return app
