"""Harness eval cấp-ký-tự (L13) — port khái niệm từ legalbenchrag.

Ground-truth = span ký tự rời nhau. Precision/Recall tính theo ký tự:
  overlap(a,b) = max(0, min(a_end,b_end) - max(a_start,b_start))
Dùng để đo retrieval cấp điều–khoản một cách không nhập nhằng, và sẽ mở rộng
thành benchmark 3 chiều (đúng điều–khoản / đúng hiệu lực / bắt bỏ sót).
"""
from __future__ import annotations

from dataclasses import dataclass

Span = tuple[int, int]  # [start, end)


def _overlap(a: Span, b: Span) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def _validate_disjoint(spans: list[Span]) -> None:
    s = sorted(spans)
    for i in range(1, len(s)):
        if s[i][0] < s[i - 1][1]:
            raise ValueError(f"spans chồng nhau: {s[i-1]} & {s[i]}")


@dataclass
class PRF:
    precision: float
    recall: float
    f1: float


def span_prf(retrieved: list[Span], gold: list[Span]) -> PRF:
    """P/R/F1 cấp ký tự giữa span truy xuất và span vàng (gold phải rời nhau)."""
    _validate_disjoint(gold)
    retrieved_len = sum(e - s for s, e in retrieved)
    gold_len = sum(e - s for s, e in gold)
    hit = sum(_overlap(r, g) for r in retrieved for g in gold)
    precision = hit / retrieved_len if retrieved_len else 0.0
    recall = hit / gold_len if gold_len else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return PRF(precision, recall, f1)
