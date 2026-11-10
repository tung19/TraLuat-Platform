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

    @classmethod
    def abstained(cls, reason: str, as_of: dt.date, gates=None) -> "Answer":
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
) -> Answer:
    # 1) retrieve (keep-and-mark effect_status@as_of) — rỗng → abstain
    cands = retrieve(session, query, as_of, lang=lang,
                     scope_frbr_uris=scope_frbr_uris, top_k=top_k)
    if not cands:
        return Answer.abstained("insufficient_retrieval", as_of)

    # 2) generate (LLM CHỈ từ ngữ cảnh; guard tenant + nhãn AI trong gateway)
    draft = gateway.generate(query, cands, as_of=as_of, node="answer",
                             tenant_id=tenant_id, lang=lang)
    if not draft.citations:                       # R1 sufficiency floor
        return Answer.abstained("insufficient_retrieval", as_of)

    # 3) verify từng trích dẫn (gate1/2/3b tất định + gate3 NLI tuỳ chọn)
    g = ground(session, draft.text, as_of,
               [c.unit_eid for c in draft.citations], lang, nli)
    if g.abstain:
        return Answer.abstained(g.reason, as_of, gates=g.gates)

    # 4) R3: điều trích đang chờ quan hệ huỷ (repeals/replaces/amends) → caveat
    caveat = any(repo.pending_destructive_relation(session, e) for e in g.supported_eids)

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
    )
