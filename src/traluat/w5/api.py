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

from .auth import decode_context
from .metrics import Metrics
from .pages import (
    _DIRECTORY_HTML,
    _GRAPH_HTML,
    _INDEX_HTML,
    _REVIEW_HTML,
    _TOOLS_HTML,
    _i18n,
)
from .service import LegalService
from .tenancy import MissingTenant, TenantContext, require_role


class AnalyzeRequest(BaseModel):
    facts: str
    as_of: str                       # ISO date
    parties: list[str] | None = None
    # I3: tình tiết LUÔN client-sensitive (không có cờ client_data).
    # B5: local_available do service health-probe, không nhận từ client.


class ReviewRequest(BaseModel):
    text: str
    rules: list[dict] | None = None   # [{name, any_of:[...]}], None → playbook mặc định


class SubscribeRequest(BaseModel):
    frbr: str                          # văn bản muốn theo dõi (FR-09)
    channel: str | None = None         # record|webhook|email (mặc định record)
    target: str | None = None          # URL webhook / email


class LookupRequest(BaseModel):        # FR-11 Q&A grounded (KB công)
    query: str
    as_of: str
    lang: str = "vi"


class SummarizeRequest(BaseModel):     # FR-14 tóm tắt grounded (KB công)
    topic: str
    as_of: str
    lang: str = "vi"


class DraftRequest(BaseModel):         # FR-34/15 soạn đơn/HĐ (tình tiết khách → local)
    kind: str
    facts: str
    as_of: str
    lang: str = "vi"


class AdviseRequest(BaseModel):        # FR-08 tư vấn tuân thủ (hoạt động khách → local)
    activity: str
    as_of: str
    lang: str = "vi"


class JudgmentRequest(BaseModel):      # FR-03 second-opinion (CN-03 high-risk)
    cited_eids: list[str]
    expected_governing: list[str]
    as_of: str
    cited_precedents: list[str] | None = None   # CN-04: án lệ bản án đã viện


_REQUIRED = object()


def parse_date(s: str | None, *, default=_REQUIRED) -> dt.date | None:
    """Parse ngày ISO → lỗi CLIENT (422), không phải 500. `default` cho field tuỳ chọn;
    thiếu khi bắt buộc → 422 (F4: ngày sai/thiếu là lỗi input, không phải server hỏng)."""
    if not s:
        if default is _REQUIRED:
            raise HTTPException(422, "thiếu ngày (cần YYYY-MM-DD)")
        return default
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise HTTPException(422, f"ngày không hợp lệ: {s!r} (cần YYYY-MM-DD)")


# playbook rà soát mặc định (FR Review / omission moat #2) — chuyên gia mở rộng (L14).
_DEFAULT_REVIEW_RULES = [
    {"name": "bảo mật", "any_of": ["bảo mật", "giữ bí mật"]},
    {"name": "giải quyết tranh chấp", "any_of": ["trọng tài", "tòa án có thẩm quyền"]},
    {"name": "bất khả kháng", "any_of": ["bất khả kháng", "force majeure"]},
    {"name": "chấm dứt hợp đồng", "any_of": ["chấm dứt", "đơn phương chấm dứt"]},
]


# FR-18 — i18n UI: thay nhãn VI→EN khi ?lang=en (nội dung pháp lý vẫn theo `lang` API).


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

    def need(ctx: TenantContext, *roles: str) -> None:
        try:
            require_role(ctx, *roles)
        except PermissionError as e:
            raise HTTPException(403, str(e))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index(lang: str = "vi"):       # W7 Experience + FR-18 song ngữ (?lang=en)
        return _i18n(_INDEX_HTML, lang)

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics_ep():                  # observability — scrape Prometheus
        return app.state.metrics.render()

    @app.get("/tools", response_class=HTMLResponse)
    def tools_page(lang: str = "vi"):  # FR-11/36/34 + FR-18 song ngữ (?lang=en)
        return _i18n(_TOOLS_HTML, lang)

    @app.get("/directory", response_class=HTMLResponse)
    def directory_page():              # FR-39 — bản đồ bấm chọn toạ độ → danh bạ gần
        return _DIRECTORY_HTML

    @app.get("/graph", response_class=HTMLResponse)
    def graph_view():                  # FR-37 — vẽ đồ thị quan hệ quy phạm (Cytoscape)
        return _GRAPH_HTML

    @app.get("/doc")
    def doc(frbr: str, as_of: str | None = None,
            ctx: TenantContext = Depends(auth), svc: LegalService = Depends(get_service)):
        # Điều hướng trích dẫn — VĂN BẢN TẠI NGÀY T (L12).
        a = parse_date(as_of, default=dt.date.today())
        return {"frbr": frbr, "as_of": a.isoformat(), "text": svc.document_as_of(frbr, a)}

    @app.get("/review", response_class=HTMLResponse)
    def review_page():                 # L12 — UI rà soát, highlight điều khoản bỏ sót
        return _REVIEW_HTML

    @app.post("/review")
    def review(body: ReviewRequest, ctx: TenantContext = Depends(auth),
               svc: LegalService = Depends(get_service)):
        need(ctx, "lawyer", "reviewer", "owner")
        return [f.__dict__ for f in svc.review(body.text, body.rules or _DEFAULT_REVIEW_RULES)]

    @app.get("/review/queue")
    def review_queue(ctx: TenantContext = Depends(auth),
                     svc: LegalService = Depends(get_service)):
        need(ctx, "reviewer", "owner")
        return [{"id": r.id, "type": r.relation_type, "confidence": r.confidence,
                 "basis": r.confidence_basis} for r in svc.review_queue()]

    @app.post("/review/queue/{rel_id}/approve")
    def review_approve(rel_id: int, ctx: TenantContext = Depends(auth),
                       svc: LegalService = Depends(get_service)):
        need(ctx, "reviewer", "owner")
        svc.approve_relation(rel_id)
        return {"approved": rel_id}

    @app.get("/directory/nearby")
    def directory_nearby(lat: float, lon: float, radius_m: float = 5000,
                         kind: str | None = None, ctx: TenantContext = Depends(auth),
                         svc: LegalService = Depends(get_service)):
        # FR-39 — danh bạ LS/công chứng/toà gần toạ độ (KB công, không tình tiết khách).
        hits = svc.nearby(lat, lon, radius_m, kind=kind)
        return [{"id": h.entry.id, "kind": h.entry.kind, "name": h.entry.name,
                 "address": h.entry.address, "phone": h.entry.phone,
                 "lat": h.lat, "lon": h.lon,
                 "distance_m": round(h.distance_m, 1)} for h in hits]

    @app.post("/alerts/subscribe")
    def alerts_subscribe(body: SubscribeRequest, ctx: TenantContext = Depends(auth),
                         svc: LegalService = Depends(get_service)):
        # FR-09 — theo dõi 1 văn bản; luật đổi → Alert (bảng khách, RLS theo tenant).
        need(ctx, "lawyer", "reviewer", "owner")
        import uuid as _uuid

        from .alerts import subscribe
        from .rls import set_tenant
        set_tenant(svc.s, ctx.tenant_id)
        sub = subscribe(svc.s, _uuid.UUID(ctx.tenant_id), body.frbr,
                        channel=body.channel or "record", target=body.target)
        return {"subscribed": body.frbr, "id": sub.id, "channel": sub.channel}

    @app.get("/alerts")
    def alerts_list(ctx: TenantContext = Depends(auth),
                    svc: LegalService = Depends(get_service)):
        # Hộp thư cảnh báo của tenant — RLS cô lập (không thấy alert tenant khác).
        import sqlalchemy as _sa

        from .models import Alert
        from .rls import set_tenant
        set_tenant(svc.s, ctx.tenant_id)
        rows = svc.s.scalars(
            _sa.select(Alert).order_by(Alert.created_at.desc())).all()
        return [{"id": a.id, "frbr": a.frbr_uri, "change": a.change,
                 "detail": a.detail, "delivered": a.delivered,
                 "created_at": a.created_at.isoformat() if a.created_at else None}
                for a in rows]

    @app.get("/graph/central")
    def graph_central(ctx: TenantContext = Depends(auth),
                      svc: LegalService = Depends(get_service)):
        # GDS PageRank 'luật trọng tâm' {eid: score} — chỉ khi Neo4j cấu hình; else {}.
        return svc.graph_central(app.state.neo4j_driver)

    @app.get("/graph/{eid}")
    def graph(eid: str, as_of: str | None = None, hops: int = 1,
              ctx: TenantContext = Depends(auth), svc: LegalService = Depends(get_service)):
        # Đồ thị quan hệ quy phạm quanh 1 điều (KB công) — FR-37 visualize.
        return svc.neighborhood(eid, parse_date(as_of, default=None), hops)

    @app.post("/analyze")
    def analyze(
        body: AnalyzeRequest,
        ctx: TenantContext = Depends(auth),
        svc: LegalService = Depends(get_service),
    ):
        need(ctx, "lawyer", "reviewer", "owner")
        resp = svc.analyze_case(body.facts, body.parties, parse_date(body.as_of), ctx)
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

    @app.post("/lookup")
    def lookup(body: LookupRequest, ctx: TenantContext = Depends(auth),
               svc: LegalService = Depends(get_service)):
        # FR-11 — hỏi–đáp pháp lý KB CÔNG (không tình tiết khách) → egress có thể ra Claude.
        need(ctx, "viewer", "lawyer", "reviewer", "owner")
        resp = svc.lookup(body.query, parse_date(body.as_of), ctx, lang=body.lang)
        a = resp.answer
        return {
            "answered": resp.answered, "trace_id": resp.trace_id, "ai_label": resp.ai_label,
            "reason": resp.reason, "route": {"destination": resp.route.destination.value},
            "abstain": a.abstain if a else True,
            "text": (a.text if a and not a.abstain else ""),
            "citations": (a.citations if a else []),
        }

    @app.post("/summarize")
    def summarize(body: SummarizeRequest, ctx: TenantContext = Depends(auth),
                  svc: LegalService = Depends(get_service)):
        # FR-14 — tóm tắt quy định pháp luật (KB công, grounded cite-or-abstain).
        need(ctx, "viewer", "lawyer", "reviewer", "owner")
        resp = svc.summarize(body.topic, parse_date(body.as_of), ctx, lang=body.lang)
        a = resp.answer
        return {
            "answered": resp.answered, "trace_id": resp.trace_id, "ai_label": resp.ai_label,
            "reason": resp.reason, "route": {"destination": resp.route.destination.value},
            "abstain": a.abstain if a else True,
            "summary": (a.text if a and not a.abstain else ""),
            "citations": (a.citations if a else []),
        }

    @app.post("/draft")
    def draft(body: DraftRequest, ctx: TenantContext = Depends(auth),
              svc: LegalService = Depends(get_service)):
        # FR-34/15 — soạn đơn/HĐ từ template, GROUNDED. Tình tiết khách → CHỈ local gateway
        # (I3 residency, R2 no-failover): local down → abstain, KHÔNG ra Claude.
        # FR-34/15 — soạn đơn/HĐ. Tình tiết khách → egress LOCAL trong service (R2).
        need(ctx, "lawyer", "reviewer", "owner")
        d, tid = svc.draft(body.kind, body.facts, parse_date(body.as_of), ctx, lang=body.lang)
        return {"abstain": d.abstain, "reason": d.reason, "text": d.text,
                "template_id": d.template_id, "citations": d.citations,
                "ai_label": d.ai_label, "route": "local", "trace_id": tid}

    @app.post("/advise")
    def advise(body: AdviseRequest, ctx: TenantContext = Depends(auth),
               svc: LegalService = Depends(get_service)):
        # FR-08 — tư vấn tuân thủ: hoạt động DN = dữ liệu khách → egress LOCAL trong service.
        need(ctx, "lawyer", "reviewer", "owner")
        a, tid = svc.advise(body.activity, parse_date(body.as_of), ctx, lang=body.lang)
        return {"abstain": a.abstain, "reason": a.reason, "advice": a.advice,
                "citations": a.citations, "ai_label": a.ai_label, "route": "local",
                "trace_id": tid, "hitl_required": True}   # high-stakes → người xác nhận

    @app.get("/deadline")
    def deadline(kind: str, start: str, as_of: str | None = None,
                 ctx: TenantContext = Depends(auth), svc: LegalService = Depends(get_service)):
        # FR-35.13 — thời hiệu/thời hạn tố tụng@as_of (neo điều luật, lùi ngày nghỉ).
        need(ctx, "viewer", "lawyer", "reviewer", "owner")
        a = parse_date(as_of, default=dt.date.today())
        try:
            r = svc.deadline(kind, parse_date(start), a)
        except LookupError as e:
            raise HTTPException(404, str(e))
        return {"kind": r.kind, "moc_bat_dau": r.moc_bat_dau.isoformat(),
                "deadline": r.deadline.isoformat(), "value": r.value, "unit": r.unit,
                "source_eid": r.source_eid, "as_of": a.isoformat(),
                "rolled_from": r.rolled_from.isoformat() if r.rolled_from else None}

    @app.get("/compare")
    def compare(frbr: str, a: str, b: str, lang: str = "vi",
                ctx: TenantContext = Depends(auth), svc: LegalService = Depends(get_service)):
        # FR-36 — so MỘT văn bản tại HAI ngày bất kỳ (bitemporal diff, KB công).
        need(ctx, "viewer", "lawyer", "reviewer", "owner")
        try:
            diffs = svc.compare(frbr, parse_date(a), parse_date(b), lang)
        except LookupError as e:
            raise HTTPException(404, str(e))
        return {"frbr": frbr, "as_of_a": a, "as_of_b": b,
                "changes": [{"eid": u.eid, "change": u.change, "a": u.before, "b": u.after}
                            for u in diffs]}

    @app.post("/judgment")
    def judgment(body: JudgmentRequest, ctx: TenantContext = Depends(auth),
                 svc: LegalService = Depends(get_service)):
        # FR-03 — second-opinion bản án (CN-03 high-risk → audit + HITL trong service).
        need(ctx, "lawyer", "reviewer", "owner")
        f, tid = svc.judgment(body.cited_eids, body.expected_governing,
                              parse_date(body.as_of), ctx,
                              cited_precedents=body.cited_precedents)
        return {"flagged": f.flagged, "reason": f.reason,
                "missing_binding": f.missing_binding,
                "missing_precedents": f.missing_precedents,   # CN-04 án lệ ràng buộc
                "ai_label": True, "trace_id": tid,
                "hitl_required": True}            # CN-03: con người quyết định cuối

    return app
