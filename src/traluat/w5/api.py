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
Điều: <input id="eid" value="nd99__dieu_5" size="20">
as_of: <input id="asof" type="date" value="2022-01-01">
hops: <input id="hops" type="number" value="2" min="1" max="3" size="2">
<button onclick="load()">Vẽ</button>
Token: <input id="tok" size="24" placeholder="Bearer JWT">
<span id="flt" class="lg"></span>
<small id="szmode"></small>
</div>
<div id="cy"></div>
<script>
const COL={cites:'#64748b',guides:'#2563eb',repeals:'#b91c1c',replaces:'#ca8a04',conflicts:'#db2777',hierarchy:'#16a34a'};
const enabled=new Set(Object.keys(COL));          // filter theo loại
let cy, central={}, raw={nodes:[],edges:[]};
// checkbox filter loại quan hệ
document.getElementById('flt').innerHTML=Object.entries(COL).map(([k,v])=>
  `<label style="background:${v};cursor:pointer"><input type=checkbox checked onchange="tog('${k}',this.checked)">${k}</label>`).join('');
function tog(t,on){on?enabled.add(t):enabled.delete(t);draw();}
function hdr(){return {'Authorization':'Bearer '+document.getElementById('tok').value}}
async function fetchGraph(e){const q=new URLSearchParams({as_of:asof.value,hops:hops.value});
  const r=await fetch('/graph/'+encodeURIComponent(e)+'?'+q,{headers:hdr()});
  if(!r.ok){alert('Lỗi '+r.status);return null}return r.json();}
function merge(d){const ne=new Set(raw.nodes.map(n=>n.eid));
  for(const n of d.nodes) if(!ne.has(n.eid)){raw.nodes.push(n);ne.add(n.eid);}
  const ee=new Set(raw.edges.map(e=>e.src+'>'+e.dst+'>'+e.type));
  for(const e of d.edges){const k=e.src+'>'+e.dst+'>'+e.type;if(!ee.has(k)){raw.edges.push(e);ee.add(k);}}}
function sizeOf(eid,indeg,maxc){
  if(maxc>0 && central[eid]!=null) return 14+40*(central[eid]/maxc);   // PageRank (GDS)
  return 14+Math.min(indeg*7,40);                                       // fallback in-degree
}
function draw(){
  const edges=raw.edges.filter(e=>enabled.has(e.type));
  const indeg={}; for(const e of edges) indeg[e.dst]=(indeg[e.dst]||0)+1;
  const show=new Set(); edges.forEach(e=>{show.add(e.src);show.add(e.dst);});
  if(center) show.add(center);
  const maxc=Math.max(0,...Object.values(central));
  const els=[];
  for(const n of raw.nodes) if(show.has(n.eid))
    els.push({data:{id:n.eid,label:n.label||n.eid,sz:sizeOf(n.eid,indeg[n.eid]||0,maxc)},classes:n.eid===center?'ctr':''});
  for(const e of edges) els.push({data:{id:e.src+'>'+e.dst+'>'+e.type,source:e.src,target:e.dst,type:e.type}});
  document.getElementById('szmode').textContent = maxc>0?'kích thước = PageRank (GDS)':'kích thước = in-degree';
  if(cy)cy.destroy();
  cy=cytoscape({container:document.getElementById('cy'),elements:els,
   style:[
    {selector:'node',style:{'label':'data(label)','font-size':'10px','background-color':'#334155','color':'#0f172a','text-valign':'bottom','text-wrap':'wrap','text-max-width':'120px','width':'data(sz)','height':'data(sz)'}},
    {selector:'node.ctr',style:{'background-color':'#2563eb','border-width':3,'border-color':'#1e40af'}},
    {selector:'edge',style:{'width':2,'curve-style':'bezier','target-arrow-shape':'triangle','line-color':ele=>COL[ele.data('type')]||'#94a3b8','target-arrow-color':ele=>COL[ele.data('type')]||'#94a3b8','label':'data(type)','font-size':'8px','color':'#64748b'}}],
   layout:{name:'cose',animate:false}});
  cy.on('tap','node',async ev=>{const d=await fetchGraph(ev.target.id());if(d){merge(d);draw();}});
}
let center=null;
async function load(){const d=await fetchGraph(eid.value);if(!d)return;
  raw={nodes:[],edges:[]};center=d.center;merge(d);
  try{const r=await fetch('/graph/central',{headers:hdr()});central=r.ok?await r.json():{};}catch(e){central={};}
  draw();}
</script>
<style>#flt label{font-size:.72rem;padding:.1rem .4rem;border-radius:.3rem;color:#fff;margin-right:.2rem}
#flt input{margin-right:.2rem}</style></body></html>"""


def get_service() -> LegalService:   # placeholder — create_app/ test override
    raise RuntimeError("get_service chưa cấu hình")


def create_app(*, jwt_secret: str, service_provider, metrics: Metrics | None = None,
               neo4j_driver=None) -> FastAPI:
    app = FastAPI(title="TraLuat API")
    app.dependency_overrides[get_service] = service_provider
    app.state.metrics = metrics or Metrics()
    app.state.neo4j_driver = neo4j_driver   # None → /graph/central trả {} (fallback degree)

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

    @app.get("/graph/central")
    def graph_central(ctx: TenantContext = Depends(auth)):
        # GDS PageRank 'luật trọng tâm' {eid: score} — chỉ khi Neo4j cấu hình; else {}.
        drv = app.state.neo4j_driver
        if drv is None:
            return {}
        from ..w2.graph_neo4j import gds_pagerank
        return dict(gds_pagerank(drv))

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
