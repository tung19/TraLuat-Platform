"""EgressPolicy (C1 + R2) — dữ liệu khách KHÔNG rời VN; fail-closed.

Phân loại theo PROVENANCE (điểm nhập: KB vs upload khách), KHÔNG đoán theo nội dung.
Bất kỳ phần nào không chắc public → coi là client_sensitive (fail-closed) → vLLM
local trong VN. R2 (chaos): local DOWN → DENY/HITL, TUYỆT ĐỐI không failover sang
Claude cho dữ liệu nhạy cảm (failover = vi phạm NĐ 356 âm thầm).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

PUBLIC_KB = "public_kb"          # nhãn provenance của KB luật công khai


class DataClass(str, Enum):
    PUBLIC_KB = "public_kb"
    CLIENT_SENSITIVE = "client_sensitive"


class LLMDestination(str, Enum):
    LOCAL = "local"              # vLLM trong VN
    CLAUDE = "claude"            # API nước ngoài — chỉ dữ liệu công
    DENY = "deny"               # không route an toàn → abstain/HITL


@dataclass
class RouteDecision:
    data_class: DataClass
    destination: LLMDestination
    reason: str


class EgressPolicy:
    def __init__(self, *, claude_allowed_for_public: bool = True) -> None:
        self.claude_allowed = claude_allowed_for_public

    def classify(self, provenances: list[str]) -> DataClass:
        # fail-closed: rỗng / có bất kỳ nhãn ≠ public_kb → client_sensitive
        if provenances and all(p == PUBLIC_KB for p in provenances):
            return DataClass.PUBLIC_KB
        return DataClass.CLIENT_SENSITIVE

    def decide(
        self, data_class: DataClass, *, local_available: bool, claude_available: bool = True,
    ) -> RouteDecision:
        if data_class == DataClass.CLIENT_SENSITIVE:
            if local_available:
                return RouteDecision(data_class, LLMDestination.LOCAL, "sensitive→local")
            # ★ R2: local down → KHÔNG failover sang Claude; queue HITL
            return RouteDecision(data_class, LLMDestination.DENY, "local_down:hitl_queue")
        # public_kb: ưu tiên Claude NẾU có sẵn; không thì fallback local; else deny
        if self.claude_allowed and claude_available:
            return RouteDecision(data_class, LLMDestination.CLAUDE, "public→claude")
        if local_available:
            return RouteDecision(data_class, LLMDestination.LOCAL, "public→local")
        return RouteDecision(data_class, LLMDestination.DENY, "no_route")
