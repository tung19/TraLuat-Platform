"""BgeM3Embedder — impl THẬT của Embedder port (BAAI/bge-m3, 1024d, MIT).

Import lười (torch nặng) → KHÔNG export ở w3/__init__; dùng:
    from traluat.w3.embed_bge import BgeM3Embedder
Chạy MPS (Apple GPU) nếu có, else CPU. safetensors-only (bge-m3 ship safetensors).
Nối vào `retrieve(embedder=...)` để truy xuất DENSE (ngữ nghĩa) thay vì chỉ lexical.
"""

from __future__ import annotations

_MODEL = "BAAI/bge-m3"


class BgeM3Embedder:
    dim = 1024

    def __init__(self, model_name: str = _MODEL, device: str | None = None) -> None:
        import torch
        from sentence_transformers import SentenceTransformer

        if device is None:
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = device
        # KHÔNG dùng weight pickle (pickle-RCE) — sentence-transformers nạp safetensors.
        self._model = SentenceTransformer(model_name, device=device)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vecs = self._model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        return [v.tolist() for v in vecs]
