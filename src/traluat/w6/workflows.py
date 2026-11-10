"""W6 Capability/Workflow (L9) — đóng gói engine thành service composable.

Mỗi service là lát 'việc đã xong' bán được, dựng TRÊN W2/W3/W4 (không làm lại lõi).
Slice: ComplianceDiffService (so văn bản tại 2 ngày — moat bitemporal) +
JudgmentAnalysisService (H6 second-opinion, chỉ chiều ràng-buộc-được, else abstain).
"""

from __future__ import annotations

import datetime as dt
import unicodedata
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..w2 import repo
from ..w2.models import Document, Unit


@dataclass
class RequiredClauseRule:
    name: str
    any_of: list[str]        # điều khoản coi là CÓ nếu thấy ≥1 từ khoá


@dataclass
class ReviewFinding:
    rule: str
    status: str              # present | missing
    evidence: str = ""


class ReviewService:
    """Rà soát văn bản theo RequiredClauseRule — bắt điều khoản BỎ SÓT (moat #2
    omission). Deterministic keyword (playbook do chuyên gia định; nâng bằng ML sau)."""

    def review(self, text: str, rules: list[RequiredClauseRule]) -> list[ReviewFinding]:
        low = unicodedata.normalize("NFC", text).lower()
        out = []
        for r in rules:
            hit = next((k for k in r.any_of if k.lower() in low), None)
            out.append(ReviewFinding(r.name, "present" if hit else "missing", hit or ""))
        return out


@dataclass
class UnitDiff:
    eid: str
    change: str              # added | removed | modified
    before: str | None
    after: str | None


class ComplianceDiffService:
    """So MỘT văn bản tại hai mốc — điều nào thêm/bỏ/sửa (moat: bitemporal diff)."""

    def __init__(self, session: Session) -> None:
        self.s = session

    def diff(self, frbr_uri: str, as_of_a: dt.date, as_of_b: dt.date,
             lang: str = "vi") -> list[UnitDiff]:
        doc = self.s.scalar(sa.select(Document).where(Document.frbr_uri == frbr_uri))
        if doc is None:
            raise LookupError(f"document không tồn tại: {frbr_uri}")
        eids = list(self.s.scalars(sa.select(Unit.eid).where(Unit.document_id == doc.id)))
        out: list[UnitDiff] = []
        for eid in eids:
            a = repo.reconstruct_as_of(self.s, eid, as_of_a, lang)
            b = repo.reconstruct_as_of(self.s, eid, as_of_b, lang)
            if a == b:
                continue
            change = "added" if a is None else "removed" if b is None else "modified"
            out.append(UnitDiff(eid, change, a, b))
        return out


@dataclass
class DraftResult:
    abstain: bool
    reason: str = ""
    text: str = ""
    template_id: int | None = None
    citations: list[str] = field(default_factory=list)
    ai_label: bool = True


class PetitionDraftService:
    """FR-34 — soạn đơn từ TEMPLATE, GROUNDED (chỉ-từ-template + điều luật truy xuất),
    cite-or-abstain, nhãn AI. Dữ liệu khách → egress local (qua gateway truyền vào)."""

    def __init__(self, session: Session, *, gateway, nli=None) -> None:
        self.s = session
        self.gateway = gateway
        self.nli = nli

    def draft(self, kind: str, facts: str, as_of: dt.date, *,
              tenant_id: str | None = None, lang: str = "vi", top_k: int = 5) -> DraftResult:
        from ..w1.templates import match_templates
        from ..w3 import ground, retrieve

        tpls = match_templates(self.s, kind=kind, lang=lang)
        if not tpls:
            return DraftResult(True, reason="no_template")
        tpl = tpls[0]
        cands = retrieve(self.s, facts, as_of, lang=lang, top_k=top_k)
        prompt = f"MẪU ĐƠN:\n{tpl.body}\n\nTÌNH TIẾT:\n{facts}\n\nĐiền mẫu, viện dẫn điều luật."
        d = self.gateway.generate(prompt, cands, as_of=as_of, node="draft",
                                  tenant_id=tenant_id, lang=lang)
        allowed = {c.unit_eid for c in cands}
        cited = [c.unit_eid for c in d.citations if c.unit_eid in allowed]
        g = ground(self.s, d.text, as_of, cited, lang, self.nli)
        if g.abstain:
            return DraftResult(True, reason=g.reason, text=d.text, template_id=tpl.id)
        return DraftResult(False, text=d.text, template_id=tpl.id, citations=g.supported_eids)


@dataclass
class JudgmentFinding:
    flagged: bool
    reason: str              # "" nếu không cờ
    missing_binding: list[str]   # eid điều ràng buộc đúng tình huống mà bản án KHÔNG áp


class JudgmentAnalysisService:
    """H6 second-opinion — CHỈ cờ 'điểm vênh' ở chiều RÀNG BUỘC ĐƯỢC: điều/án lệ
    đúng tình huống, còn hiệu lực @ngày xử, mà bản án không viện dẫn. Chiều tuỳ nghi
    (mức bồi thường, đánh giá chứng cứ) → KHÔNG tự kết luận 'thẩm phán sai' (abstain).
    """

    def __init__(self, session: Session) -> None:
        self.s = session

    def analyze(self, cited_eids: list[str], expected_governing: list[str],
                as_of: dt.date) -> JudgmentFinding:
        from ..w2.bitemporal import EffectStatus
        cited = set(cited_eids)
        missing = []
        for eid in expected_governing:
            if eid in cited:
                continue
            # chỉ cờ nếu điều CÒN HIỆU LỰC tại ngày xử (ràng buộc được)
            if repo.effect_status(self.s, eid, as_of) in (
                    EffectStatus.IN_FORCE, EffectStatus.TRANSITIONAL_APPLIES):
                missing.append(eid)
        if missing:
            return JudgmentFinding(
                True, "bản án không viện dẫn điều còn hiệu lực đúng tình huống", missing)
        return JudgmentFinding(False, "", [])
