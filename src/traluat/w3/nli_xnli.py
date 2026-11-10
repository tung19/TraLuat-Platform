"""XNLIVerifier — impl THẬT của NLIVerifier port (gate3 'hỗ trợ pháp lý').

mDeBERTa-v3 XNLI đa ngữ (xử lý tiếng Việt). premise = nguyên văn điều luật,
hypothesis = khẳng định → P(entailment) ≥ θ → 'promote', else 'hold' (KHÔNG veto,
đúng spec gate3). Legal-NLI chuyên biệt chưa có → dùng NLI chung làm stand-in;
cắm model fine-tune pháp lý sau = đổi model_name, không đụng lõi. Import lười.
"""

from __future__ import annotations

_MODEL = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"


class XNLIVerifier:
    def __init__(self, model_name: str = _MODEL, threshold: float = 0.5,
                 device: str | None = None) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if device is None:
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = device
        self.threshold = threshold
        self._tok = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_name).to(device).eval()
        self._ent = next(i for i, l in self._model.config.id2label.items()
                         if "entail" in l.lower())

    def _probs(self, premise: str, hypothesis: str):
        import torch

        inputs = self._tok(premise, hypothesis, return_tensors="pt",
                           truncation=True, max_length=512).to(self.device)
        with torch.no_grad():
            return self._model(**inputs).logits.softmax(-1)[0]

    def supports(self, claim: str, source: str) -> str:
        # gate3: source (premise) hỗ trợ claim (hypothesis)? entail ≥ θ → promote.
        return "promote" if self._probs(source, claim)[self._ent].item() >= self.threshold else "hold"

    def label(self, premise: str, hypothesis: str) -> str:
        """Nhãn NLI argmax: 'entailment' | 'neutral' | 'contradiction' (3-way)."""
        probs = self._probs(premise, hypothesis)
        idx = int(probs.argmax().item())
        return self._model.config.id2label[idx].lower()
