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
<title>TraLuat</title><style>
body{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem}
.badge{font-size:.75rem;padding:.1rem .4rem;border-radius:.3rem;color:#fff}
.in_force{background:#16a34a}.expired_citable{background:#b91c1c}.transitional_applies{background:#ca8a04}
.cite{font-family:monospace;background:#f1f5f9;padding:.1rem .3rem;border-radius:.2rem}
.abstain{color:#b91c1c;font-weight:600}.ai{font-size:.75rem;color:#64748b}
textarea,input{font:inherit}</style></head>
<body><h1>TraLuat — trợ lý pháp lý</h1>
<p><a href="/graph">→ Đồ thị quan hệ quy phạm (FR-37)</a></p>
<p>Nhập tình tiết + <b>ngày sự kiện</b> (không phải ngày hỏi). Kết quả có
<b>trích dẫn điều–khoản tại ngày T</b> kèm trạng thái hiệu lực, hoặc
<b>abstain</b> khi không đủ căn cứ. Mọi output gắn nhãn AI (Luật 71/2025).</p>
<form id="f">
<textarea id="facts" rows="4" style="width:100%" placeholder="tình tiết vụ việc...">vốn pháp định tối thiểu của doanh nghiệp</textarea>
<label>as_of <input id="asof" type="date" value="2022-01-01"></label>
<button>Phân tích</button>
<p class="ai">Token JWT: <input id="tok" size="40" placeholder="dán Bearer token"></p></form>
<div id="out"></div>
<script>
const esc=s=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
f.onsubmit=async e=>{e.preventDefault();out.innerHTML='<p>...</p>';
 const r=await fetch('/analyze',{method:'POST',headers:{'Content-Type':'application/json',
  'Authorization':'Bearer '+tok.value},
  body:JSON.stringify({facts:facts.value,as_of:asof.value})});
 const d=await r.json();
 if(r.status!==200){out.innerHTML='<p class=abstain>Lỗi '+r.status+': '+esc(JSON.stringify(d))+'</p>';return;}
 let h='<p class=ai>🤖 nội dung AI · route='+d.route.destination+' · trace='+d.trace_id+'</p>';
 for(const p of (d.parties||[])){
   if(p.abstain){h+='<p class=abstain>⛔ '+esc(p.party)+': abstain ('+esc(p.reason)+')</p>';continue;}
   h+='<p><b>'+esc(p.party)+'</b>: '+esc(p.relief)+'</p><p>Căn cứ: ';
   for(const c of (p.citations||[])) h+='<span class=cite>'+esc(c)+'</span> ';
   h+='</p>';}
 out.innerHTML=h;};
</script></body></html>"""


class AnalyzeRequest(BaseModel):
    facts: str
    as_of: str                       # ISO date
    parties: list[str] | None = None
    # I3: tình tiết LUÔN client-sensitive (không có cờ client_data).
    # B5: local_available do service health-probe, không nhận từ client.


_GRAPH_HTML = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>TraLuat — Đồ thị quy phạm</title>
<script src="https://unpkg.com/cytoscape@3/dist/cytoscape.min.js"></script>
<style>
body{font-family:system-ui,sans-serif;margin:0}
#bar{padding:.6rem 1rem;border-bottom:1px solid #e2e8f0;display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}
#cy{width:100vw;height:calc(100vh - 110px)}
input{font:inherit;padding:.2rem .4rem}
.lg span{font-size:.72rem;padding:.1rem .4rem;border-radius:.3rem;color:#fff;margin-right:.3rem}
small{color:#64748b}
</style></head><body>
<div id="bar">
<b>TraLuat · đồ thị quy phạm</b>
Điều: <input id="eid" value="nd99__dieu_5" size="22">
as_of: <input id="asof" type="date" value="2022-01-01">
hops: <input id="hops" type="number" value="2" min="1" max="3" size="2">
<button onclick="load()">Vẽ</button>
Token: <input id="tok" size="28" placeholder="Bearer JWT">
<span class="lg" id="lg"></span>
</div>
<div id="cy"></div>
<p style="padding:0 1rem"><small>Click một node để mở rộng lân cận. Mũi tên = chiều quan hệ (src→dst). Màu theo loại.</small></p>
<script>
const COL={cites:'#64748b',guides:'#2563eb',repeals:'#b91c1c',replaces:'#ca8a04',conflicts:'#db2777',hierarchy:'#16a34a'};
document.getElementById('lg').innerHTML=Object.entries(COL).map(([k,v])=>`<span style="background:${v}">${k}</span>`).join('');
let cy;
function hdr(){return {'Authorization':'Bearer '+document.getElementById('tok').value}}
async function fetchGraph(eid){
  const q=new URLSearchParams({as_of:asof.value,hops:hops.value});
  const r=await fetch('/graph/'+encodeURIComponent(eid)+'?'+q,{headers:hdr()});
  if(!r.ok){alert('Lỗi '+r.status);return null}
  return r.json();
}
function toElements(d,center){
  const els=[];const seen=new Set();
  for(const n of d.nodes){if(seen.has(n.eid))continue;seen.add(n.eid);
    els.push({data:{id:n.eid,label:n.label||n.eid},classes:n.eid===center?'ctr':''});}
  for(const e of d.edges) els.push({data:{id:e.src+'>'+e.dst+'>'+e.type,source:e.src,target:e.dst,type:e.type}});
  return els;
}
function render(els){
  cy=cytoscape({container:document.getElementById('cy'),elements:els,
   style:[
    {selector:'node',style:{'label':'data(label)','font-size':'10px','background-color':'#0f172a','color':'#0f172a','text-valign':'bottom','text-wrap':'wrap','text-max-width':'120px','width':16,'height':16}},
    {selector:'node.ctr',style:{'background-color':'#2563eb','width':24,'height':24,'font-weight':'bold'}},
    {selector:'edge',style:{'width':2,'curve-style':'bezier','target-arrow-shape':'triangle','line-color':ele=>COL[ele.data('type')]||'#94a3b8','target-arrow-color':ele=>COL[ele.data('type')]||'#94a3b8','label':'data(type)','font-size':'8px','color':'#64748b'}}],
   layout:{name:'cose',animate:false}});
  cy.on('tap','node',async ev=>{const d=await fetchGraph(ev.target.id());if(!d)return;
    cy.add(toElements(d,null).filter(e=>!cy.getElementById(e.data.id).length));
    cy.layout({name:'cose',animate:false}).run();});
}
async function load(){const d=await fetchGraph(eid.value);if(!d)return;
  if(cy)cy.destroy();render(toElements(d,d.center));}
</script></body></html>"""


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

    @app.get("/graph", response_class=HTMLResponse)
    def graph_view():                  # FR-37 — vẽ đồ thị quan hệ quy phạm (Cytoscape)
        return _GRAPH_HTML

    @app.get("/graph/{eid}")
    def graph(eid: str, as_of: str | None = None, hops: int = 1,
              ctx: TenantContext = Depends(auth), svc: LegalService = Depends(get_service)):
        # Đồ thị quan hệ quy phạm quanh 1 điều (KB công) — FR-37 visualize.
        from ..w2 import repo
        a = dt.date.fromisoformat(as_of) if as_of else None
        return repo.neighborhood(svc.s, eid, a, max_hops=min(hops, 3))

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
