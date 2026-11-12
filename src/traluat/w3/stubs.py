"""Stub tất định cho các port — pipeline chạy ngay, thay bằng model thật sau.

HashEmbedder: embedding băm (ổn định, cùng dim) — chỗ-giữ cho bge-m3.
NoopReranker: giữ nguyên thứ tự — chỗ-giữ cho cross-encoder.
HoldNLI: luôn 'hold' — chỉ cho phép nguyên câu trích xuất, không hỗ trợ diễn giải.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from .ports import NLIVerdict

_TOK = re.compile(r"\w+", re.UNICODE)


def _toks(s: str) -> set[str]:
    return {t for t in _TOK.findall(unicodedata.normalize("NFC", s).lower()) if len(t) > 1}


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
    demo_only = True

    def supports(self, claim: str, source: str) -> NLIVerdict:
        return "hold"


class KeywordNLIVerifier:
    """STUB tất định — 'promote' nếu phần lớn từ của claim có trong nguồn, else 'hold'.

    Chỗ-giữ cho NLI thật (ViLegalBERT / LLM-as-NLI structured {support, span}).
    Không phải verifier pháp lý; chỉ dùng test wiring/đo overlap. Grounding không
    dùng PROMOTE của stub này để chấp nhận diễn giải.
    """

    demo_only = True

    def __init__(self, threshold: float = 0.6) -> None:
        self.threshold = threshold

    def supports(self, claim: str, source: str) -> NLIVerdict:
        ct = _toks(claim)
        if not ct:
            return "hold"
        return "promote" if len(ct & _toks(source)) / len(ct) >= self.threshold else "hold"
