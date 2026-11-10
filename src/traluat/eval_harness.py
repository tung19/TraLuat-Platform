"""Eval harness (L13) — KHUNG đo chất lượng, cắm gold set vào là chạy.

3 chiều (spec W3 §4): correct-article (P/R eid) · correct-effectivity (as-of trả
đúng điều còn hiệu lực) · catch-omission (recall điều bắt buộc). + abstention 4-cell
+ Brier. Gold set (effectivity/omission/conflict) là MOAT eval — chuyên gia label,
cắm qua GoldCase. Harness này KHÔNG tự sinh gold; nó chấm answer_fn trên gold.

char-level P/R (port legalbenchrag) có ở `char_pr` cho gold dạng span ký tự.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy.orm import Session

from .w3 import Answer


@dataclass
class GoldCase:
    case_id: str
    query: str
    as_of: dt.date
    gold_eids: list[str] = field(default_factory=list)       # điều ĐÚNG phải trích
    required_eids: list[str] = field(default_factory=list)   # omission: phải phủ hết
    expect_abstain: bool = False                             # câu 'luật im' / bẫy
    tags: list[str] = field(default_factory=list)            # correct-article|effectivity|…


@dataclass
class CaseResult:
    case_id: str
    answered: bool
    abstain_correct: bool
    precision: float | None
    recall: float | None
    omission_recall: float | None
    confidence: float
    tags: list[str]


def _pr(pred: set[str], gold: set[str]) -> tuple[float | None, float | None]:
    if not gold:
        return None, None
    inter = len(pred & gold)
    p = inter / len(pred) if pred else 0.0
    r = inter / len(gold)
    return p, r


def char_pr(pred_spans: list[tuple[int, int]], gold_spans: list[tuple[int, int]]):
    """P/R cấp KÝ TỰ (legalbenchrag) — spans half-open, giả định rời & cùng tài liệu."""
    def total(ss): return sum(e - s for s, e in ss)
    overlap = sum(max(0, min(pe, ge) - max(ps, gs))
                  for ps, pe in pred_spans for gs, ge in gold_spans)
    tp, tg = total(pred_spans), total(gold_spans)
    return (overlap / tp if tp else 0.0), (overlap / tg if tg else 0.0)


@dataclass
class EvalReport:
    results: list[CaseResult]

    def by_tag(self) -> dict[str, dict]:
        agg: dict[str, list[CaseResult]] = defaultdict(list)
        for r in self.results:
            for t in (r.tags or ["(untagged)"]):
                agg[t].append(r)
        out = {}
        for tag, rs in agg.items():
            ps = [r.precision for r in rs if r.precision is not None]
            rc = [r.recall for r in rs if r.recall is not None]
            out[tag] = {
                "n": len(rs),
                "precision": sum(ps) / len(ps) if ps else None,
                "recall": sum(rc) / len(rc) if rc else None,
            }
        return out

    def abstention_cells(self) -> dict[str, int]:
        """4-cell: nên-trả × nên-abstain vs đã-trả × đã-abstain."""
        cells = {"answer_ok": 0, "answer_when_should_abstain": 0,
                 "abstain_ok": 0, "abstain_when_should_answer": 0}
        for r in self.results:
            if r.answered:
                cells["answer_ok" if r.abstain_correct else "answer_when_should_abstain"] += 1
            else:
                cells["abstain_ok" if r.abstain_correct else "abstain_when_should_answer"] += 1
        return cells

    def brier(self) -> float | None:
        """Brier trên câu nên-trả: outcome = đã phủ đủ gold chưa."""
        scored = [r for r in self.results if r.recall is not None]
        if not scored:
            return None
        return sum((r.confidence - (1.0 if (r.recall or 0) >= 1.0 else 0.0)) ** 2
                   for r in scored) / len(scored)

    def summary(self) -> str:
        lines = ["— EVAL REPORT —", f"cases: {len(self.results)}"]
        for tag, m in sorted(self.by_tag().items()):
            p = "—" if m["precision"] is None else f"{m['precision']:.2f}"
            rc = "—" if m["recall"] is None else f"{m['recall']:.2f}"
            lines.append(f"  [{tag}] n={m['n']} P={p} R={rc}")
        lines.append(f"abstention: {self.abstention_cells()}")
        b = self.brier()
        lines.append(f"brier: {'—' if b is None else f'{b:.3f}'}")
        return "\n".join(lines)


def run_eval(
    session: Session,
    cases: list[GoldCase],
    answer_fn: Callable[[Session, GoldCase], Answer],
) -> EvalReport:
    """Chấm answer_fn trên gold. answer_fn thường gói answer_question(... gateway=...)."""
    results: list[CaseResult] = []
    for c in cases:
        ans = answer_fn(session, c)
        answered = not ans.abstain
        abstain_correct = (ans.abstain == c.expect_abstain)
        pred = set(ans.citations)
        p, r = _pr(pred, set(c.gold_eids))
        om = None
        if c.required_eids:
            req = set(c.required_eids)
            om = len(pred & req) / len(req)
        results.append(CaseResult(
            c.case_id, answered, abstain_correct, p, r, om, ans.confidence, c.tags,
        ))
    return EvalReport(results)
