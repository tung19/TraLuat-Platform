"""W4 — Reasoning engine (tầng điều phối). Slice-1: Auditor HARD-GATE (moat W4).

Auditor = cổng TIỀN-output: mỗi điều ứng viên qua 3 cổng — (1) trích dẫn có thật ·
(3) ngày hiệu lực (in_force, cắm W2; KHÔNG filter cứng chuyển tiếp) · (2) áp dụng
theo TỪNG yếu tố cấu thành (element-wise) — rồi PRUNE án lệ mất điểm tựa. Cổng 1&3
tất định (rẻ) chạy trước cổng 2 (tốn |elements|+1 lời gọi). W4 KHÔNG tự làm retrieval/
NLI cấp claim — đó là W3. Spec: docs/specs/w4-reasoning-engine.md §3.

Defer (cần model/gold): element judge LLM thật (ElementJudge port có stub), Researcher/
Adjudicator per-party, Reasoner đa vai LangGraph, nối GroundingService hậu-draft.
"""

from .types import Article, AuditEntry, AuditResult, Precedent
from .auditor import Auditor, ElementJudge, KeywordElementJudge, prune_unsupported
from .reasoner import Adjudication, CaseInput, PartyResult, ReasoningEngine
from .multi_role import DebateResult, MultiRoleReasoner, RoleConfig, Utterance

__all__ = [
    "Article", "Precedent", "AuditEntry", "AuditResult",
    "Auditor", "ElementJudge", "KeywordElementJudge", "prune_unsupported",
    "CaseInput", "PartyResult", "Adjudication", "ReasoningEngine",
    "MultiRoleReasoner", "RoleConfig", "Utterance", "DebateResult",
]
