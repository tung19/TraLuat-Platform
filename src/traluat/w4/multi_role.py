"""Reasoner đa vai (§5) — luật sư⇄kiểm sát⇄thẩm phán⇄bộ ngành, vòng tranh biện.

Bất biến: **Auditor chạy trên MỌI phát ngôn** — căn cứ một vai viện dẫn phải qua 3
cổng (§3) trước khi vào biên bản; căn cứ rớt bị gạch (ghi transcript). ⇒ không vai
nào 'thắng' bằng điều hết hiệu lực / không áp dụng.

Stop-condition DETERMINISTIC (siết PAKTON fragile): dừng khi tập verified ỔN ĐỊNH
qua trọn một lượt (set-equality) HOẶC chạm max_rounds — KHÔNG sentinel/embedding.
H4: memoize audit theo (eid, as_of) → mỗi điều audit MỘT lần/vụ (chặn bùng nổ chi
phí). Vai nên dùng model KHÁC verifier (cross-provider) — cấu hình, ghi chú.

Viết lại sạch từ pattern LangGraph (PAKTON Apache-2.0, khác domain) — KHÔNG copy.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..w3.ports import LLMGateway, NLIVerifier
from .auditor import ElementJudge
from .reasoner import Adjudication, CaseInput, ReasoningEngine


@dataclass
class RoleConfig:
    name: str
    query_focus: str = ""          # lệch góc nhìn khi thu bằng chứng (stub; prompt thật sau)


# vai = cấu hình (role prompt + scope), KHÔNG hardcode — sau lấy từ JurisdictionPack (W6)
DEFAULT_ROLES = [
    RoleConfig("lawyer", "quyền lợi"),
    RoleConfig("prosecutor", "vi phạm nghĩa vụ"),
    RoleConfig("judge", ""),
    RoleConfig("ministry", "thủ tục hành chính"),
]


@dataclass
class Utterance:
    role: str
    round: int
    proposed_eids: list[str]
    verified_eids: list[str]       # qua Auditor gate
    struck_eids: list[str]         # bị gạch (ghi để giải trình)


@dataclass
class DebateResult:
    adjudication: Adjudication
    transcript: list[Utterance] = field(default_factory=list)
    rounds: int = 0
    converged: bool = False        # True=dừng do hội tụ · False=chạm max_rounds
    thread_id: str = ""


class MultiRoleReasoner:
    def __init__(
        self, session: Session, *, gateway: LLMGateway,
        roles: list[RoleConfig] | None = None, nli: NLIVerifier | None = None,
        element_judge: ElementJudge | None = None,
        elements_by_eid: dict[str, list[str]] | None = None,
        max_rounds: int = 3, top_k: int = 8,
    ) -> None:
        self.engine = ReasoningEngine(
            session, gateway=gateway, nli=nli,
            element_judge=element_judge, elements_by_eid=elements_by_eid)
        self.roles = roles or DEFAULT_ROLES
        self.max_rounds = max_rounds
        self.top_k = top_k

    def run(
        self, case: CaseInput, as_of: dt.date, *,
        tenant_id: str | None = None, case_id: str = "case", lang: str = "vi",
    ) -> DebateResult:
        # thread_id từ tenant+case (KHÔNG timestamp — truy vết + chống va chạm)
        thread_id = f"tenant:{tenant_id or 'none'}:{case_id}"
        memo: dict[str, object | None] = {}       # H4: (eid) → Article | None (audit 1 lần/vụ)
        pool: dict[str, object] = {}              # verified tích luỹ
        chunk_all: dict[str, object] = {}
        transcript: list[Utterance] = []
        converged = False
        rnd = 0

        for rnd in range(1, self.max_rounds + 1):
            added = False
            for role in self.roles:
                query = f"{case.facts} {role.query_focus}".strip()
                articles, cbe = self.engine._research(query, as_of, lang, self.top_k)
                chunk_all.update(cbe)
                proposed = [a.unit_eid for a in articles]

                # Auditor trên phát ngôn — chỉ audit eid MỚI (memoize per vụ)
                new = [a for a in articles if a.unit_eid not in memo]
                res = self.engine.auditor.audit(case.facts, as_of, new, lang=lang)
                for a in res.verified_articles:
                    memo[a.unit_eid] = a
                for e in res.trail:
                    if not e.accepted:
                        memo.setdefault(e.unit_eid, None)

                verified_eids = [e for e in proposed if memo.get(e) is not None]
                struck = [e for e in proposed if memo.get(e) is None]
                for e in verified_eids:
                    if e not in pool:
                        pool[e] = memo[e]
                        added = True
                transcript.append(Utterance(role.name, rnd, proposed, verified_eids, struck))

            if not added:                 # hội tụ: trọn lượt không thêm căn cứ verified
                converged = True
                break

        verified = list(pool.values())
        party = self.engine._adjudicate(
            "(hợp nghị)", case.facts, as_of, verified, chunk_all, lang, tenant_id)
        adj = Adjudication(
            parties=[party], verified_articles=verified, verified_precedents=[],
            audit_trail=[], draft=party.relief, ai_label=True)
        return DebateResult(adj, transcript, rnd, converged, thread_id)
