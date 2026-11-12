"""Vòng grounding orchestrated (L5→L6→L7) — ráp retrieve + gateway + gates + abstain.

Bất biến (spec §2): LLM CHỈ trả lời từ đoạn đã truy xuất; mọi trích dẫn qua verify
hoặc ABSTAIN. Đây là khung — cắm gateway thật (ClaudeLLMGateway) + nli thật là xong,
không đụng lõi. Stub (EchoLLMGateway + HoldNLI) cho chạy ngay.

Defer có chủ đích: as_of_map đa-mốc/lex-mitior (§1b — ở đây 1 anchor), confidence
HIỆU CHỈNH (F10 — ở đây tỉ lệ cổng qua, chưa calibrate), Faith-Search repair (§2).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..w2 import repo
from ..w2.bitemporal import EffectStatus
from .as_of import AsOfPlan, resolve_as_of
from .grounding import GateResult, ground
from .ports import LLMGateway, NLIVerifier
from .retrieval import retrieve

CAVEAT_CAP = 0.6   # R3: trần confidence khi có quan hệ huỷ đang chờ duyệt


@dataclass
class Answer:
    abstain: bool
    reason: str = ""                      # lý do abstain ("" nếu trả lời)
    text: str = ""
    citations: list[str] = field(default_factory=list)
    effect_status: dict[str, EffectStatus] = field(default_factory=dict)  # eid → status@as_of
    as_of: dt.date | None = None
    confidence: float = 0.0
    caveat: bool = False                  # R3: điều trích có quan hệ huỷ đang chờ duyệt
    ai_label: bool = True
    gates: list[GateResult] = field(default_factory=list)
    review_context: list[dict[str, str]] = field(default_factory=list)
    needs_human: bool = False
    sources: list[dict] = field(default_factory=list)
    model: str | None = None
    is_demo: bool = False

    @classmethod
    def abstained(cls, reason: str, as_of: dt.date, gates=None) -> Answer:
        return cls(abstain=True, reason=reason, as_of=as_of, gates=gates or [])


def answer_question(
    session: Session,
    query: str,
    *,
    as_of: dt.date,
    gateway: LLMGateway,
    nli: NLIVerifier | None = None,
    tenant_id: str | None = None,
    lang: str = "vi",
    scope_frbr_uris: list[str] | None = None,
    top_k: int = 8,
    extra_anchors: list[dt.date] | None = None,
    plan_caveat: bool = False,
    node: str = "answer",            # "answer" | "summary" (FR-14) → model-tier router
    retriever=None,
) -> Answer:
    # B1: pin MỘT known_as_of (tx-time) cho cả request → retrieve và verify thấy
    # cùng một snapshot, không lệch nếu có tx-version commit giữa chừng.
    known = repo._db_now(session)

    # 1) retrieve tại primary + các mốc phụ (§1b đa-mốc), hợp nhất theo eid (giữ
    #    bản primary trước → text trích dẫn theo mốc chính). rỗng → abstain.
    anchors = [as_of, *(extra_anchors or [])]
    seen: dict[tuple[str, dt.date], object] = {}
    cands = []
    for a in anchors:
        for rc in (retriever or retrieve)(session, query, a, lang=lang,
                           scope_frbr_uris=scope_frbr_uris, top_k=top_k, known_as_of=known):
            key = (rc.unit_eid, rc.chunk.as_of)
            if key not in seen:
                seen[key] = rc
                cands.append(rc)
    if not cands:
        return Answer.abstained("insufficient_retrieval", as_of)

    # Preserve every retrieved version for human comparison. Fetching a newer
    # criminal provision does not establish that it applies retroactively or is
    # more favourable; never silently choose a legal conclusion at one anchor.
    if len(set(anchors)) > 1 or plan_caveat:
        reason = "multiple_anchors_require_review" if len(set(anchors)) > 1 else "uncertain_anchor_requires_review"
        answer = Answer.abstained(reason, as_of)
        answer.needs_human = True
        answer.caveat = True
        answer.review_context = [
            {"unit_eid": rc.unit_eid, "anchor": rc.chunk.as_of.isoformat(),
             "text": rc.chunk.span_text, "effect_status": rc.effect_status.value}
            for rc in cands]
        return answer

    # 2) generate (LLM CHỈ từ ngữ cảnh; guard tenant + nhãn AI trong gateway)
    draft = gateway.generate(query, cands, as_of=as_of, node=node,
                             tenant_id=tenant_id, lang=lang)
    if not draft.citations:                       # R1 sufficiency floor
        return Answer.abstained("insufficient_retrieval", as_of)

    # ★ bất biến §2: LLM CHỈ được trích từ đoạn ĐÃ truy xuất — loại trích dẫn
    # ngoài ngữ cảnh (chống viện dẫn từ kiến thức tham số). Rỗng sau lọc → abstain.
    allowed = {rc.unit_eid for rc in cands}
    cited = [c for c in draft.citations if c.unit_eid in allowed]
    if len(cited) != len(draft.citations) and cited:
        return Answer.abstained("citation_outside_context", as_of)

    # 3) verify từng trích dẫn (gate1/2/3b tất định + gate3 NLI tuỳ chọn) — cùng known
    g = ground(session, draft.text, as_of, cited, lang, nli, known_as_of=known)
    if g.abstain:
        return Answer.abstained(g.reason, as_of, gates=g.gates)

    # 4) caveat: R3 (điều trích đang chờ quan hệ huỷ) HOẶC mốc không chắc (plan HITL)
    caveat = plan_caveat or any(
        repo.pending_destructive_relation(session, e) for e in g.supported_eids)

    passed = [gt for gt in g.gates if gt.passed]
    conf = len(passed) / len(g.gates)             # F10: placeholder, chưa calibrate
    if nli and any(gt.gate3_nli == "promote" for gt in passed):
        conf = min(1.0, conf + 0.1)
    if caveat:
        conf = min(conf, CAVEAT_CAP)

    return Answer(
        abstain=False, text=draft.text, citations=g.supported_eids,
        effect_status={gt.unit_eid: gt.status for gt in passed},
        as_of=as_of, confidence=conf, caveat=caveat,
        ai_label=draft.ai_label, gates=g.gates,
        model=draft.model, is_demo=draft.model == "echo-stub",
        sources=[{"unit_eid": rc.unit_eid, "frbr_uri": rc.chunk.frbr_uri,
                  "title": rc.chunk.struct_header, "text": rc.chunk.span_text,
                  "as_of": as_of.isoformat(), "effect_status": rc.effect_status.value}
                 for rc in cands if rc.unit_eid in g.supported_eids],
    )


def answer_with_resolution(
    session: Session,
    query: str,
    *,
    gateway: LLMGateway,
    question_type: str = "general",
    event_date: dt.date | None = None,
    today: dt.date | None = None,
    nli: NLIVerifier | None = None,
    tenant_id: str | None = None,
    lang: str = "vi",
    scope_frbr_uris: list[str] | None = None,
    top_k: int = 8,
    retriever=None,
) -> tuple[Answer, AsOfPlan]:
    """Giải mốc (event-date-first + lex-mitior) rồi trả lời. Verify tại mốc CHÍNH
    (ngày sự kiện); mốc phụ (luật-nay cho hình sự) chỉ WIDEN retrieval để tầng sau
    so favorability. plan.needs_human → caveat (mốc không chắc)."""
    plan = resolve_as_of(query, question_type, event_date=event_date, today=today)
    extras = [a for a in plan.anchors if a != plan.primary]
    ans = answer_question(
        session, query, as_of=plan.primary, gateway=gateway, nli=nli,
        tenant_id=tenant_id, lang=lang, scope_frbr_uris=scope_frbr_uris,
        top_k=top_k, extra_anchors=extras, plan_caveat=plan.needs_human, retriever=retriever,
    )
    return ans, plan
