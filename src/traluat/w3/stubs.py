"""Stub tất định cho các port — pipeline chạy ngay, thay bằng model thật sau.

HashEmbedder: embedding băm (ổn định, cùng dim) — chỗ-giữ cho bge-m3.
NoopReranker: giữ nguyên thứ tự — chỗ-giữ cho cross-encoder.
HoldNLI: luôn 'hold' (không PROMOTE, không veto) — gate3 trung tính tới khi cắm NLI thật.
"""

from __future__ import annotations

import hashlib

from .ports import NLIVerdict


class HashEmbedder:
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).digest()
            vec = [(h[i % len(h)] / 255.0) for i in range(self.dim)]
            out.append(vec)
        return out


class NoopReranker:
    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        return [1.0 for _ in candidates]


class HoldNLI:
    def supports(self, claim: str, source: str) -> NLIVerdict:
        return "hold"
