"""Model-tier router (stack §5) — chọn model/effort theo NODE, không một-model-cho-tất.

Nguyên tắc: Opus (hard/judgment: answer/adjudicator), Sonnet (bulk: element/draft/
aggregate), Haiku (route/phân loại rẻ). Cross-provider: verifier KHÁC họ answerer
(F4) — verifier_model trỏ model khác. sensitive=True → vLLM local (residency) thay
Claude. Thuần cấu hình (tất định) → test được không cần API.
"""

from __future__ import annotations

from dataclasses import dataclass

OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-5-5"
HAIKU = "claude-haiku-5-5"
LOCAL = "vllm-local"                 # placeholder — endpoint vLLM trong VN


@dataclass
class ModelChoice:
    model: str
    effort: str
    provider: str = "anthropic"      # 'anthropic' | 'local'


# node → (model, effort) cho dữ liệu KHÔNG nhạy cảm (được ra Claude).
_ROUTES: dict[str, tuple[str, str]] = {
    "answer": (OPUS, "high"),
    "adjudicator": (OPUS, "high"),       # phán quyết — nặng, chính xác
    "auditor.element": (SONNET, "medium"),  # bulk element-wise — rẻ hơn
    "auditor.aggregate": (SONNET, "medium"),
    "draft": (SONNET, "medium"),
    "route": (HAIKU, "low"),             # phân loại/định tuyến — rẻ nhất
}
_DEFAULT = (OPUS, "high")


def route(node: str, *, sensitive: bool = False) -> ModelChoice:
    """Chọn model/effort theo node. sensitive → local vLLM (dữ liệu khách không ra VN)."""
    if sensitive:
        return ModelChoice(LOCAL, "high", provider="local")
    model, effort = _ROUTES.get(node, _DEFAULT)
    return ModelChoice(model, effort, provider="anthropic")
