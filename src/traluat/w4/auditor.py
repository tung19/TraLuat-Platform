"""Auditor HARD-GATE (§3) — 3 cổng + element-wise + prune. Cổng 1&3 tất định (W2).

Thứ tự tối ưu chi phí: cổng 1 (tồn tại) → cổng 3 (hiệu lực, deterministic) → cổng 2
(element-wise, |elements| lời gọi). Điều rớt cổng 1/3 KHÔNG tốn lời gọi element.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from typing import Protocol, runtime_checkable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..w2 import repo
from ..w2.bitemporal import EffectStatus
from ..w2.models import Unit
from .types import Article, AuditEntry, AuditResult, Precedent

_APPLICABLE = {EffectStatus.IN_FORCE, EffectStatus.TRANSITIONAL_APPLIES}
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
# hư từ hay gặp — bỏ khi so khớp element↔facts (stub)
_STOP = {"và", "hoặc", "của", "các", "những", "được", "là", "có", "trong", "khi",
         "theo", "cho", "với", "một", "này", "đó", "phải", "để", "từ"}


def _tokens(text: str) -> set[str]:
    toks = _TOKEN_RE.findall(unicodedata.normalize("NFC", text).lower())
    return {t for t in toks if t not in _STOP and len(t) > 1}


@runtime_checkable
class ElementJudge(Protocol):
    def judge(self, element: str, law_text: str, party_facts: str) -> bool | None:
        """True thoả · False không thoả · None không phân giải được (→ needs_review)."""
        ...


class KeywordElementJudge:
    """STUB tất định — yếu tố coi là thoả nếu từ khoá của nó có trong tình tiết.

    Chỗ-giữ cho LLMElementJudge thật (structured {satisfied, span} + temp=0, neo span,
    cross-provider → HITL khi bất đồng). Test điều khiển được bằng câu chữ tình tiết.
    """

    def judge(self, element: str, law_text: str, party_facts: str) -> bool | None:
        et = _tokens(element)
        if not et:
            return None
        return bool(et & _tokens(party_facts))


def verify_article(
    judge: ElementJudge, art: Article, party_facts: str,
) -> tuple[bool, str]:
    """Cổng 2 — áp dụng theo TỪNG yếu tố (KHÔNG holistic yes/no).

    Áp dụng ⇔ mọi yếu tố thoả và không yếu tố nào 'needs_review'. Không yếu tố →
    áp dụng (không có checklist để chặn). unsatisfied/needs_review → ghi rõ.
    """
    if not art.elements:
        return True, "no_elements"
    satisfied, unsatisfied, needs_review = [], [], []
    for el in art.elements:
        v = judge.judge(el, art.text or "", party_facts)
        (satisfied if v is True else unsatisfied if v is False else needs_review).append(el)
    applies = not unsatisfied and not needs_review
    detail = f"satisfied={satisfied} unsatisfied={unsatisfied} needs_review={needs_review}"
    return applies, detail


def prune_unsupported(
    verified_articles: list[Article], candidate_precedents: list[Precedent],
) -> list[Precedent]:
    """Giữ án lệ chỉ khi còn tựa vào ≥1 điều ĐÃ verify (chống analogy-drift)."""
    live = {a.unit_eid for a in verified_articles}
    return [p for p in candidate_precedents if any(e in live for e in p.cited_unit_eids)]


class Auditor:
    def __init__(self, session: Session, element_judge: ElementJudge | None = None) -> None:
        self.s = session
        self.judge = element_judge or KeywordElementJudge()

    def _exists(self, eid: str) -> bool:
        return self.s.scalar(sa.select(Unit.id).where(Unit.eid == eid)) is not None

    def audit(
        self, party_facts: str, as_of: dt.date,
        candidate_articles: list[Article],
        candidate_precedents: list[Precedent] | None = None,
        lang: str = "vi",
    ) -> AuditResult:
        verified: list[Article] = []
        trail: list[AuditEntry] = []

        for art in candidate_articles:
            # ── CỔNG 1: trích dẫn có thật ──────────────────────────────────
            if not self._exists(art.unit_eid):
                trail.append(AuditEntry(art.unit_eid, False, 1, "citation_unreachable"))
                continue

            # ── CỔNG 3: ngày hiệu lực (deterministic, rẻ) ─────────────────
            text, status = repo.citable_text(self.s, art.unit_eid, as_of, lang)
            if status not in _APPLICABLE:   # EXPIRED/NOT_YET/ABSENT → loại (keep-and-mark ở W3)
                trail.append(AuditEntry(art.unit_eid, False, 3, "temporally_invalid",
                                        detail=status.value))
                continue
            if art.text and text and art.text.strip() != text.strip():   # H3 version-match
                trail.append(AuditEntry(art.unit_eid, False, 3, "version_mismatch"))
                continue
            if status == EffectStatus.TRANSITIONAL_APPLIES and "transitional" not in art.flags:
                art.flags.append("transitional")   # GIỮ + đánh dấu, KHÔNG filter cứng

            # ── CỔNG 2: element-wise (tốn lời gọi — chạy sau cùng) ────────
            art.text = art.text or text
            ok, detail = verify_article(self.judge, art, party_facts)
            if ok:
                verified.append(art)
                trail.append(AuditEntry(art.unit_eid, True, None, "", detail, list(art.flags)))
            else:
                trail.append(AuditEntry(art.unit_eid, False, 2, "not_applicable", detail))

        verified_precedents = prune_unsupported(verified, candidate_precedents or [])
        return AuditResult(verified, verified_precedents, trail)
