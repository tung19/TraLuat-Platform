"""Resume must never reuse an applicability decision for changed inputs."""
import datetime as dt

import pytest

from traluat.w2.bitemporal import EffectStatus
from traluat.w3 import EchoLLMGateway
from traluat.w4 import CaseInput, InMemoryCheckpointer, MultiRoleReasoner, RoleConfig
from traluat.w4.types import Article

D = dt.date(2020, 1, 1)
EID = "law__dieu_1"
TEXT = "Chỉ bên đáp ứng điều kiện mới được hưởng quyền."


class FakeSession:
    def scalar(self, *args, **kwargs):
        return 1


class Judge:
    checkpoint_version = "judge-v1"

    def __init__(self):
        self.calls = 0

    def judge(self, element, law, facts):
        self.calls += 1
        return facts == "eligible"


def reasoner(judge, elements=None):
    mr = MultiRoleReasoner(FakeSession(), gateway=EchoLLMGateway(), roles=[RoleConfig("judge")],
                          element_judge=judge, elements_by_eid={EID: elements or ["eligibility"]},
                          max_rounds=1)
    mr.engine._research = lambda *args: ([Article(EID, D, TEXT, elements=elements or ["eligibility"])], {})
    return mr


@pytest.fixture()
def mock_knowledge(monkeypatch):
    snapshot = {"version": "snapshot-1"}
    monkeypatch.setattr("traluat.w4.multi_role.knowledge_fingerprint", lambda s: snapshot["version"])
    monkeypatch.setattr("traluat.w4.auditor.repo.citable_text",
                        lambda *a, **kw: (TEXT, EffectStatus.IN_FORCE))
    monkeypatch.setattr("traluat.w4.multi_role.repo.reconstruct_as_of", lambda *a, **kw: TEXT)
    return snapshot


def test_identical_input_and_snapshot_can_resume_without_reauditing(mock_knowledge):
    cp = InMemoryCheckpointer()
    first, second = Judge(), Judge()
    reasoner(first).run(CaseInput("eligible"), D, tenant_id="t1", case_id="c1", checkpointer=cp)
    result = reasoner(second).run(CaseInput("eligible"), D, tenant_id="t1", case_id="c1", checkpointer=cp)
    assert first.calls == 1 and second.calls == 0
    assert result.adjudication.verified_articles


def test_changed_facts_invalidate_prior_applicability(mock_knowledge):
    cp = InMemoryCheckpointer()
    reasoner(Judge()).run(CaseInput("eligible"), D, tenant_id="t1", case_id="c1", checkpointer=cp)
    judge = Judge()
    result = reasoner(judge).run(CaseInput("ineligible"), D, tenant_id="t1", case_id="c1", checkpointer=cp)
    assert judge.calls == 1 and not result.adjudication.verified_articles
    assert result.adjudication.parties[0].abstain


@pytest.mark.parametrize("changed", ["snapshot", "date", "elements", "judge_version", "lang"])
def test_changed_audit_dependencies_are_reaudited(mock_knowledge, changed):
    cp = InMemoryCheckpointer()
    reasoner(Judge()).run(CaseInput("eligible"), D, tenant_id="t1", case_id="c1", checkpointer=cp)
    judge, anchor, lang, elements = Judge(), D, "vi", None
    if changed == "snapshot":
        mock_knowledge["version"] = "snapshot-2"
    elif changed == "date":
        anchor = dt.date(2021, 1, 1)
    elif changed == "elements":
        elements = ["new reviewed checklist"]
    elif changed == "judge_version":
        judge.checkpoint_version = "judge-v2"
    else:
        lang = "en"
    reasoner(judge, elements).run(CaseInput("eligible"), anchor, tenant_id="t1", case_id="c1",
                                  lang=lang, checkpointer=cp)
    assert judge.calls == 1


def test_unversioned_custom_judge_is_never_reused(mock_knowledge):
    cp = InMemoryCheckpointer()
    judge = Judge()
    judge.checkpoint_version = None
    mr = reasoner(judge)
    for _ in range(2):
        mr.run(CaseInput("eligible"), D, tenant_id="t1", case_id="c1", checkpointer=cp)
    assert judge.calls == 2
