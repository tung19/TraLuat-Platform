"""Read-only isolated audit reproductions. No pytest/conftest or database access.

Run from workspace: PYTHONPATH=src .venv/bin/python /private/tmp/traluat-audit-ai-repros.py
"""
import datetime as dt
from unittest.mock import patch

from traluat.core.eval_harness import GoldCase, run_eval
from traluat.w2.bitemporal import EffectStatus
from traluat.w2.models import PrecedentRow
from traluat.w3 import Answer
from traluat.w3.chunker import Chunk
from traluat.w3.gateway import BaseLLMGateway, EchoLLMGateway
from traluat.w3.grounding import _facts, ground
from traluat.w3.orchestrator import answer_question, answer_with_resolution
from traluat.w3.ports import Citation, LLMResult
from traluat.w3.retrieval import RetrievedChunk
from traluat.w4 import CaseInput, InMemoryCheckpointer, MultiRoleReasoner, ReasoningEngine, RoleConfig
from traluat.w4.types import Article

D = dt.date(2020, 1, 1)
EID = "law__dieu_1"


class Rows(list):
    def all(self):
        return self


class FakeSession:
    def scalar(self, *args, **kwargs):
        return 1

    def scalars(self, *args, **kwargs):
        return Rows([PrecedentRow(
            precedent_id="FUTURE-AL", cited_eids=[EID], situation="x",
            solution="future solution", effective_from=dt.date(2025, 1, 1))])


class Hold:
    def supports(self, *args):
        return "hold"


class FabricatedGateway:
    def generate(self, *args, **kwargs):
        return LLMResult(
            text="Doanh nghiệp được kinh doanh ngành bị cấm. Không cần xin phép bất kỳ cơ quan nào.",
            citations=[Citation(EID)])


source = "Doanh nghiệp không được kinh doanh ngành bị cấm."
rc = RetrievedChunk(Chunk(EID, "vi", "Điều 1", source, EffectStatus.IN_FORCE, D), 1.0, True)
with patch("traluat.w3.orchestrator.retrieve", return_value=[rc]), patch(
    "traluat.w3.grounding.repo.citable_text", return_value=(source, EffectStatus.IN_FORCE)
), patch("traluat.w3.orchestrator.repo.pending_destructive_relation", return_value=False):
    a = answer_question(FakeSession(), "kinh doanh ngành bị cấm", as_of=D,
                        gateway=FabricatedGateway(), nli=Hold())
    print("semantic_grounding", {"abstain": a.abstain, "confidence": a.confidence,
                                 "nli": a.gates[0].gate3_nli, "text": a.text})
    assert not a.abstain and a.confidence == 1.0

source = "Mức lãi suất là 0,5% mỗi tháng."
claim = "Mức lãi suất là 5% mỗi tháng."
with patch("traluat.w3.grounding.repo.citable_text", return_value=(source, EffectStatus.IN_FORCE)):
    g = ground(FakeSession(), claim, D, [EID])
    print("decimal_grounding", {"source_facts": sorted(_facts(source)),
                                "claim_facts": sorted(_facts(claim)), "abstain": g.abstain})
    assert not g.abstain

c = GoldCase("omission", "q", D, gold_eids=["eid-A"],
             required_eids=["eid-A", "eid-B"], tags=["omission"])
r = run_eval(None, [c], lambda *_: Answer(abstain=False, citations=["eid-A"], confidence=1.0))
print("omission_gate", {"article_recall": r.results[0].recall,
                        "omission_recall": r.results[0].omission_recall,
                        "gate": r.gate({"omission": 1.0})})
assert r.results[0].omission_recall == 0.5 and r.gate({"omission": 1.0})[0]


class LanguageGateway(BaseLLMGateway):
    def _draft(self, query, chunks, prompt, as_of, node, lang):
        return lang, []


gw = LanguageGateway()
a = gw.generate("query", [rc], as_of=D, lang="vi")
b = gw.generate("query", [rc], as_of=D, lang="en")
print("language_cache", {"first": a.text, "second": b.text, "same_object": a is b})
assert b.text == "vi"


class Judge:
    def __init__(self):
        self.calls = 0

    def judge(self, element, law, facts):
        self.calls += 1
        return facts == "eligible"


source = "Chỉ bên đáp ứng điều kiện mới được hưởng quyền."


def article():
    return Article(EID, D, source, elements=["eligible condition"])


cp = InMemoryCheckpointer()
with patch("traluat.w4.auditor.repo.citable_text", return_value=(source, EffectStatus.IN_FORCE)), patch(
    "traluat.w4.multi_role.repo.reconstruct_as_of", return_value=source
):
    j1 = Judge()
    mr1 = MultiRoleReasoner(FakeSession(), gateway=EchoLLMGateway(), roles=[RoleConfig("judge")],
                           element_judge=j1, elements_by_eid={EID: ["eligible condition"]}, max_rounds=1)
    mr1.engine._research = lambda *args: ([article()], {})
    mr1.run(CaseInput("eligible"), D, tenant_id="t1", case_id="c1", checkpointer=cp)
    j2 = Judge()
    mr2 = MultiRoleReasoner(FakeSession(), gateway=EchoLLMGateway(), roles=[RoleConfig("judge")],
                           element_judge=j2, elements_by_eid={EID: ["eligible condition"]}, max_rounds=1)
    mr2.engine._research = lambda *args: ([article()], {})
    second = mr2.run(CaseInput("ineligible"), D, tenant_id="t1", case_id="c1", checkpointer=cp)
    print("checkpoint_changed_facts", {"first_judge_calls": j1.calls,
                                       "second_judge_calls": j2.calls,
                                       "second_verified": [a.unit_eid for a in second.adjudication.verified_articles],
                                       "abstain": second.adjudication.parties[0].abstain})
    assert j1.calls == 1 and j2.calls == 0 and not second.adjudication.parties[0].abstain

    eng = ReasoningEngine(FakeSession(), gateway=EchoLLMGateway(), element_judge=Judge())
    eng._research = lambda *args: ([Article(EID, D, source)], {})
    adj = eng.analyze(CaseInput("case"), D)
    print("future_precedent", {"as_of": str(D), "precedent_effective_from": "2025-01-01",
                               "verified_precedents": [p.precedent_id for p in adj.verified_precedents]})
    assert adj.verified_precedents[0].precedent_id == "FUTURE-AL"


class RecordingGateway(EchoLLMGateway):
    def generate(self, query, context_chunks, **kwargs):
        self.context = [(x.unit_eid, x.chunk.span_text, str(x.chunk.as_of)) for x in context_chunks]
        return super().generate(query, context_chunks, **kwargs)


new_date = dt.date(2025, 1, 1)
old_text, new_text = "Hình phạt là 5 năm.", "Hình phạt là 1 năm."
old_rc = RetrievedChunk(Chunk(EID, "vi", "Điều 1", old_text, EffectStatus.IN_FORCE, D), 1.0, True)
new_rc = RetrievedChunk(Chunk(EID, "vi", "Điều 1", new_text, EffectStatus.IN_FORCE, new_date), 1.0, True)
gw = RecordingGateway()
with patch("traluat.w3.orchestrator.retrieve", side_effect=lambda s, q, a, **kw: [old_rc if a == D else new_rc]), patch(
    "traluat.w3.grounding.repo.citable_text", return_value=(old_text, EffectStatus.IN_FORCE)
), patch("traluat.w3.orchestrator.repo.pending_destructive_relation", return_value=False):
    ans, plan = answer_with_resolution(FakeSession(), "hành vi", gateway=gw,
                                      question_type="hinh_su", event_date=D, today=new_date)
    print("lex_mitior_context", {"lenient_fetch": plan.lenient_fetch,
                                 "context": gw.context, "answer": ans.text})
    assert plan.lenient_fetch and len(gw.context) == 1 and gw.context[0][1] == old_text
