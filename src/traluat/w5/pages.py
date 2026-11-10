"""W5 · Giao diện HTML (tách khỏi api.py — routing ≠ presentation).

Các trang server-render + i18n VI/EN. api.py chỉ import, không chứa HTML."""

from __future__ import annotations

_EN_MAP = {
    "công cụ pháp lý": "legal tools",
    "Hỏi–đáp pháp lý": "Legal Q&A", "Tóm tắt quy định": "Summarize law",
    "Thời hiệu / thời hạn tố tụng": "Limitation / procedural deadline",
    "So sánh văn bản 2 ngày": "Compare document (two dates)",
    "Soạn đơn từ mẫu": "Draft petition from template",
    "tình tiết khách → local": "client facts → local",
    "dán Bearer token": "paste Bearer token",
    "chủ đề...": "topic...", "câu hỏi...": "question...", "tình tiết...": "facts...",
    "mốc bắt đầu": "start date", "loại": "type", "bán kính": "radius",
    ">Hỏi<": ">Ask<", ">Tóm tắt<": ">Summarize<", ">Tính<": ">Compute<",
    ">So<": ">Compare<", ">Soạn<": ">Draft<",
    "TraLuat — trợ lý pháp lý": "TraLuat — legal assistant",
    "Đồ thị quy phạm": "Norm graph", "Rà soát hợp đồng": "Contract review",
    "Danh bạ geo": "Geo directory",
    "Phân tích": "Analyze", "ngày sự kiện": "event date",
}


def _i18n(html: str, lang: str) -> str:
    """Thay nhãn UI sang EN khi lang='en' (FR-18). Chèn thanh chuyển ngữ."""
    toggle = ('<p style="text-align:right;font-size:.8rem">'
              '<a href="?lang=vi">VI</a> | <a href="?lang=en">EN</a></p>')
    if lang == "en":
        for vi, en in _EN_MAP.items():
            html = html.replace(vi, en)
    return html.replace("<body>", "<body>" + toggle, 1)


_INDEX_HTML = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>TraLuat</title><style>
body{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem}
.badge{font-size:.75rem;padding:.1rem .4rem;border-radius:.3rem;color:#fff}
.in_force{background:#16a34a}.expired_citable{background:#b91c1c}.transitional_applies{background:#ca8a04}
.cite{font-family:monospace;background:#f1f5f9;padding:.1rem .3rem;border-radius:.2rem}
.abstain{color:#b91c1c;font-weight:600}.ai{font-size:.75rem;color:#64748b}
textarea,input{font:inherit}</style></head>
<body><h1>TraLuat — trợ lý pháp lý</h1>
<p><a href="/tools">→ Công cụ (hỏi-đáp · so sánh · soạn đơn)</a> · <a href="/graph">→ Đồ thị quy phạm (FR-37)</a> · <a href="/review">→ Rà soát hợp đồng</a> · <a href="/directory">→ Danh bạ geo (FR-39)</a></p>
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


_TOOLS_HTML = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>TraLuat — Công cụ</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{font-family:system-ui,sans-serif;max-width:820px;margin:1.5rem auto;padding:0 1rem}
section{border:1px solid #e2e8f0;border-radius:.5rem;padding:.8rem 1rem;margin:.8rem 0}
h2{margin:.2rem 0 .6rem;font-size:1.05rem}input,textarea,button{font:inherit}
input,textarea{padding:.25rem .4rem}.row{display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;margin:.3rem 0}
pre{background:#f8fafc;padding:.6rem;border-radius:.4rem;white-space:pre-wrap;font-size:.85rem;overflow:auto}
.cite{font-family:monospace;background:#eef2ff;padding:.05rem .3rem;border-radius:.2rem;margin-right:.2rem}
.ab{color:#b91c1c;font-weight:600}small{color:#64748b}</style></head><body>
<h1>TraLuat — công cụ pháp lý</h1>
<p class=row>Token JWT: <input id="tok" size="46" placeholder="dán Bearer token" style="flex:1"></p>

<section><h2>Hỏi–đáp pháp lý (FR-11)</h2>
<div class=row><input id="lq" size="40" placeholder="câu hỏi..." style="flex:1" value="vốn pháp định tối thiểu">
<input id="la" type="date" value="2022-01-01"><button onclick="lookup()">Hỏi</button></div>
<div id="lout"></div></section>

<section><h2>Tóm tắt quy định (FR-14)</h2>
<div class=row><input id="sq" size="40" placeholder="chủ đề..." style="flex:1" value="điều kiện kinh doanh">
<input id="sa2" type="date" value="2022-01-01"><button onclick="summarize()">Tóm tắt</button></div>
<div id="sout"></div></section>

<section><h2>⚡Thời hiệu / thời hạn tố tụng (FR-35.13)</h2>
<div class=row>loại <input id="wk" size="22" value="khang_cao_so_tham_ds">
mốc bắt đầu <input id="ws" type="date" value="2022-03-04">
as_of <input id="wa" type="date" value="2022-06-01"><button onclick="deadline()">Tính</button></div>
<div id="wout"></div></section>

<section><h2>So sánh văn bản 2 ngày (FR-36)</h2>
<div class=row>frbr <input id="cf" size="22" value="trl:vn/nd/99/2020">
T1 <input id="c1" type="date" value="2021-06-01"> T2 <input id="c2" type="date" value="2022-06-01">
<button onclick="compare()">So</button></div><div id="cout"></div></section>

<section><h2>Tư vấn tuân thủ (FR-08) · hoạt động khách → local</h2>
<textarea id="af" rows="3" style="width:100%" placeholder="mô tả hoạt động DN...">kinh doanh rượu bia nhập khẩu</textarea>
<div class=row><input id="ad" type="date" value="2022-01-01"><button onclick="advise()">Tư vấn</button></div>
<div id="aout"></div></section>

<section><h2>Soạn đơn từ mẫu (FR-34) · tình tiết khách → local</h2>
<div class=row>loại <input id="dk" size="14" value="khoi_kien">
<input id="dd" type="date" value="2022-01-01"></div>
<textarea id="df" rows="3" style="width:100%" placeholder="tình tiết...">tranh chấp hợp đồng vay</textarea>
<div class=row><button onclick="draft()">Soạn</button></div><div id="dout"></div></section>

<script>
const esc=s=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function hdr(j){const h={'Authorization':'Bearer '+document.getElementById('tok').value};
  if(j)h['Content-Type']='application/json';return h;}
function cites(a){return (a||[]).map(c=>'<span class=cite>'+esc(c)+'</span>').join('');}
async function lookup(){const o=document.getElementById('lout');o.innerHTML='...';
  const r=await fetch('/lookup',{method:'POST',headers:hdr(1),body:JSON.stringify(
    {query:lq.value,as_of:la.value})});const d=await r.json();
  if(r.status!=200){o.innerHTML='<p class=ab>Lỗi '+r.status+'</p>';return;}
  o.innerHTML=d.abstain?('<p class=ab>⛔ abstain: '+esc(d.reason)+'</p>')
    :('<pre>'+esc(d.text)+'</pre><p>'+cites(d.citations)+'</p>')
    +'<small>🤖 AI · route='+esc(d.route.destination)+' · trace='+esc(d.trace_id)+'</small>';}
async function summarize(){const o=document.getElementById('sout');o.innerHTML='...';
  const r=await fetch('/summarize',{method:'POST',headers:hdr(1),body:JSON.stringify(
    {topic:sq.value,as_of:sa2.value})});const d=await r.json();
  if(r.status!=200){o.innerHTML='<p class=ab>Lỗi '+r.status+'</p>';return;}
  o.innerHTML=d.abstain?('<p class=ab>⛔ abstain: '+esc(d.reason)+'</p>')
    :('<pre>'+esc(d.summary)+'</pre><p>'+cites(d.citations)+'</p>')
    +'<small>🤖 AI · route='+esc(d.route.destination)+'</small>';}
async function deadline(){const o=document.getElementById('wout');o.innerHTML='...';
  const q=new URLSearchParams({kind:wk.value,start:ws.value,as_of:wa.value});
  const r=await fetch('/deadline?'+q,{headers:hdr()});const d=await r.json();
  if(r.status!=200){o.innerHTML='<p class=ab>Lỗi '+r.status+': '+esc(JSON.stringify(d))+'</p>';return;}
  o.innerHTML='<p><b>Hết hạn: '+esc(d.deadline)+'</b> ('+d.value+' '+d.unit+')'
    +(d.rolled_from?(' · đã lùi từ '+esc(d.rolled_from)+' do ngày nghỉ'):'')+'<br>'
    +'<small>căn cứ '+cites([d.source_eid])+' · @'+esc(d.as_of)+'</small></p>';}
async function compare(){const o=document.getElementById('cout');o.innerHTML='...';
  const q=new URLSearchParams({frbr:cf.value,a:c1.value,b:c2.value});
  const r=await fetch('/compare?'+q,{headers:hdr()});const d=await r.json();
  if(r.status!=200){o.innerHTML='<p class=ab>Lỗi '+r.status+': '+esc(JSON.stringify(d))+'</p>';return;}
  if(!d.changes.length){o.innerHTML='<small>Không có thay đổi giữa 2 ngày.</small>';return;}
  o.innerHTML=d.changes.map(c=>'<p><span class=cite>'+esc(c.eid)+'</span> <b>'+c.change+'</b><br>'
    +'<small>T1:</small> '+esc(c.a||'∅')+'<br><small>T2:</small> '+esc(c.b||'∅')+'</p>').join('');}
async function advise(){const o=document.getElementById('aout');o.innerHTML='...';
  const r=await fetch('/advise',{method:'POST',headers:hdr(1),body:JSON.stringify(
    {activity:af.value,as_of:ad.value})});const d=await r.json();
  if(r.status!=200){o.innerHTML='<p class=ab>Lỗi '+r.status+'</p>';return;}
  o.innerHTML=d.abstain?('<p class=ab>⛔ abstain: '+esc(d.reason)+'</p>')
    :('<pre>'+esc(d.advice)+'</pre><p>'+cites(d.citations)+'</p>')
    +'<small>🤖 AI · route=local · cần người xác nhận</small>';}
async function draft(){const o=document.getElementById('dout');o.innerHTML='...';
  const r=await fetch('/draft',{method:'POST',headers:hdr(1),body:JSON.stringify(
    {kind:dk.value,facts:df.value,as_of:dd.value})});const d=await r.json();
  if(r.status!=200){o.innerHTML='<p class=ab>Lỗi '+r.status+'</p>';return;}
  o.innerHTML=d.abstain?('<p class=ab>⛔ abstain: '+esc(d.reason)+'</p>')
    :('<pre>'+esc(d.text)+'</pre><p>'+cites(d.citations)+'</p>')
    +'<small>🤖 AI · route=local</small>';}
</script></body></html>"""


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


_DIRECTORY_HTML = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>TraLuat — Danh bạ (FR-39)</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
body{font-family:system-ui,sans-serif;margin:0}
#bar{padding:.6rem 1rem;border-bottom:1px solid #e2e8f0;display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}
#wrap{display:flex;height:calc(100vh - 56px)}
#map{flex:1}#side{width:320px;overflow:auto;border-left:1px solid #e2e8f0;padding:.5rem .8rem}
input,select{font:inherit;padding:.2rem .4rem}
.item{padding:.4rem .2rem;border-bottom:1px solid #f1f5f9;cursor:pointer}
.item:hover{background:#f8fafc}.k{font-size:.7rem;color:#fff;padding:.05rem .35rem;border-radius:.3rem}
.d{color:#2563eb;font-weight:600}small{color:#64748b}
</style></head><body>
<div id="bar">
<b>TraLuat · danh bạ geo</b>
<small>bấm bản đồ để chọn toạ độ</small>
Loại: <select id="kind"><option value="">tất cả</option>
<option value="toa_an">toà án</option><option value="cong_chung">công chứng</option>
<option value="vien_ksnd">VKS</option><option value="thi_hanh_an">thi hành án</option>
<option value="co_quan">cơ quan</option></select>
Bán kính: <input id="rad" type="range" min="1" max="50" value="5"><span id="radv">5</span> km
Token: <input id="tok" size="18" placeholder="Bearer JWT">
</div>
<div id="wrap"><div id="map"></div>
<div id="side"><p><small>Chọn một điểm trên bản đồ…</small></p></div></div>
<script>
const COL={toa_an:'#16a34a',cong_chung:'#2563eb',vien_ksnd:'#b91c1c',thi_hanh_an:'#ca8a04',co_quan:'#64748b'};
const map=L.map('map').setView([10.7769,106.7009],12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);
let pick=null, hitLayer=L.layerGroup().addTo(map);
const rad=document.getElementById('rad'), radv=document.getElementById('radv');
rad.oninput=()=>{radv.textContent=rad.value; if(pick) query();};
document.getElementById('kind').onchange=()=>{if(pick)query();};
map.on('click',e=>{setPick(e.latlng.lat,e.latlng.lng);query();});
function setPick(lat,lon){
  if(pick)map.removeLayer(pick);
  pick=L.marker([lat,lon]).addTo(map).bindPopup('điểm chọn').openPopup();
}
async function query(){
  const kind=document.getElementById('kind').value;
  const q=new URLSearchParams({lat:pick.getLatLng().lat,lon:pick.getLatLng().lng,
    radius_m:rad.value*1000}); if(kind)q.set('kind',kind);
  const side=document.getElementById('side');
  const r=await fetch('/directory/nearby?'+q,{headers:{'Authorization':'Bearer '+document.getElementById('tok').value}});
  if(!r.ok){side.innerHTML='<p class=d>Lỗi '+r.status+'</p>';return;}
  const list=await r.json(); hitLayer.clearLayers();
  if(!list.length){side.innerHTML='<p><small>Không có cơ quan trong bán kính.</small></p>';return;}
  side.innerHTML='<p><b>'+list.length+'</b> kết quả trong '+rad.value+' km</p>';
  const esc=s=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  list.forEach(x=>{
    const c=COL[x.kind]||'#64748b', km=(x.distance_m/1000).toFixed(2);
    if(x.lat!=null&&x.lon!=null){
      L.circleMarker([x.lat,x.lon],{radius:7,color:c,fillColor:c,fillOpacity:.85,weight:1})
        .bindPopup('<b>'+esc(x.name)+'</b><br>'+km+' km')
        .addTo(hitLayer);
    }
    const el=document.createElement('div'); el.className='item';
    el.innerHTML='<span class=k style="background:'+c+'">'+x.kind+'</span> '
      +'<span class=d>'+km+' km</span><br>'
      +'<b>'+esc(x.name)+'</b><br><small>'+esc(x.address||'')
      +(x.phone?(' · ☎ '+esc(x.phone)):'')+'</small>';
    if(x.lat!=null&&x.lon!=null) el.onclick=()=>map.setView([x.lat,x.lon],15);
    side.appendChild(el);
  });
}
</script></body></html>"""


_REVIEW_HTML = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>TraLuat — Rà soát</title><style>
body{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem}
.f{padding:.4rem .6rem;border-radius:.3rem;margin:.3rem 0}
.present{background:#dcfce7}.missing{background:#fee2e2;font-weight:600}
textarea{width:100%}</style></head><body>
<h1>Rà soát hợp đồng — điều khoản bỏ sót</h1>
<p>Dán hợp đồng; hệ bắt điều khoản thiếu theo playbook (moat #2 omission).</p>
<textarea id="t" rows="8" placeholder="dán hợp đồng...">Hợp đồng dịch vụ. Hai bên cam kết bảo mật thông tin. Tranh chấp giải quyết tại tòa án có thẩm quyền.</textarea>
<p>Token: <input id="tok" size="36" placeholder="Bearer JWT"> <button onclick="go()">Rà soát</button></p>
<div id="out"></div>
<script>
async function go(){out.innerHTML='...';
 const r=await fetch('/review',{method:'POST',headers:{'Content-Type':'application/json',
  'Authorization':'Bearer '+tok.value},body:JSON.stringify({text:t.value})});
 if(!r.ok){out.textContent='Lỗi '+r.status;return;}
 const d=await r.json();
 out.innerHTML=d.map(f=>`<div class="f ${f.status}">${f.status==='present'?'✓':'⚠ THIẾU'} — ${f.rule}${f.evidence?' ('+f.evidence+')':''}</div>`).join('');}
</script></body></html>"""
