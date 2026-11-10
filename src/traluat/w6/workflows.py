"""W6 Capability/Workflow (L9) — đóng gói engine thành service composable.

Mỗi service là lát 'việc đã xong' bán được, dựng TRÊN W2/W3/W4 (không làm lại lõi).
Slice: ComplianceDiffService (so văn bản tại 2 ngày — moat bitemporal) +
JudgmentAnalysisService (H6 second-opinion, chỉ chiều ràng-buộc-được, else abstain).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..w2 import repo
from ..w2.models import Document, Unit


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
