"""ElementJudge THẬT (Gate 2) — NLI 3-way thay keyword stub.

Mỗi yếu tố cấu thành = một suy luận: tình tiết (premise) có kéo theo 'yếu tố thoả'
(hypothesis) không? entailment → True · contradiction → False · neutral → None
(needs_review, KHÔNG im lặng bỏ — đúng spec C1/C4). Dùng XNLI đã có; legal-NLI
fine-tune / LLM subsumption = đổi backend, không đụng Auditor.

Import lười (model nặng). LLMElementJudge (gateway JUDGE_ELEMENT_PROMPT structured
{satisfied, span}) = biến thể khi có API — cùng port.
"""

from __future__ import annotations


class NLIElementJudge:
    def __init__(self, nli=None) -> None:
        # nli: đối tượng có .label(premise, hypothesis); None → nạp XNLIVerifier.
        if nli is None:
            from ..w3.nli_xnli import XNLIVerifier
            nli = XNLIVerifier()
        self._nli = nli

    def judge(self, element: str, law_text: str, party_facts: str) -> bool | None:
        if not element.strip() or not party_facts.strip():
            return None
        label = self._nli.label(party_facts, element)   # tình tiết ⟹ yếu tố?
        if "entail" in label:
            return True
        if "contradict" in label:
            return False
        return None                                     # neutral → needs_review
