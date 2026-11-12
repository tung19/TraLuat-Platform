"""Adversarial grounding and gateway regressions; no models/network/database."""

import datetime as dt

import pytest

from traluat.w2.bitemporal import EffectStatus
from traluat.w3.chunker import Chunk
from traluat.w3.gateway import BaseLLMGateway, ClaudeLLMGateway
from traluat.w3.grounding import _facts, ground
from traluat.w3.orchestrator import answer_question, answer_with_resolution
from traluat.w3.ports import Citation, LLMResult
from traluat.w3.retrieval import RetrievedChunk

D = dt.date(2020, 1, 1)
EID = "law__dieu_1"


class FakeSession:
    def scalar(self, *args, **kwargs):
        return 1


class Verdict:
    def __init__(self, value):
        self.value = value

    def supports(self, *args):
        return self.value


def source(monkeypatch, text):
    monkeypatch.setattr("traluat.w3.grounding.repo.citable_text",
                        lambda *a, **kw: (text, EffectStatus.IN_FORCE))


@pytest.mark.parametrize(("text", "fact"), [
    ("lãi suất 0,5%", "0.5 %"),
    ("vốn 1,5 triệu đồng", "1.5 triệu"),
    ("nợ 1.000,50 đồng", "1000.5 đồng"),
    ("nợ 1.000 đồng", "1000 đồng"),
    ("lãi suất 0.5%", "0.5 %"),
    ("thay đổi -0,5%", "-0.5 %"),
    ("thay đổi +0,5%", "0.5 %"),
    ("chênh lệch -1.000 đồng", "-1000 đồng"),
    ("chênh lệch +1.000 đồng", "1000 đồng"),
    ("khoảng 5–10%", "range:5:10 %"),
    ("từ -5 đến +10%", "range:-5:10 %"),
])
def test_vietnamese_decimal_does_not_lose_digits(text, fact):
    assert _facts(text) == {fact}


def test_decimal_magnitude_error_is_rejected(monkeypatch):
    source(monkeypatch, "Mức lãi suất là 0,5% mỗi tháng.")
    g = ground(FakeSession(), "Mức lãi suất là 5% mỗi tháng.", D, [EID])
    assert g.abstain and not g.gates[0].gate3b_exact


def test_sign_and_range_boundaries_are_not_interchangeable():
    assert _facts("thay đổi -5%") != _facts("thay đổi +5%")
    assert _facts("thay đổi −5%") == _facts("thay đổi -5%")
    assert _facts("mức từ 5 đến 10%") != _facts("mức 10%")


@pytest.mark.parametrize("nli", [None, Verdict("hold"), Verdict("promote")])
def test_bare_citation_never_proves_opposite_or_additional_claim(monkeypatch, nli):
    source(monkeypatch, "Doanh nghiệp không được kinh doanh ngành bị cấm.")
    g = ground(FakeSession(), "Doanh nghiệp được kinh doanh ngành bị cấm. "
               "Không cần xin phép bất kỳ cơ quan nào.", D, [EID], nli=nli)
    assert g.abstain


def test_extracting_negation_substring_is_not_support(monkeypatch):
    source(monkeypatch, "Doanh nghiệp không được kinh doanh ngành bị cấm.")
    assert ground(FakeSession(), "được kinh doanh ngành bị cấm.", D, [EID]).abstain


def test_every_claim_needs_its_own_source(monkeypatch):
    a, b = "Doanh nghiệp phải đăng ký.", "Cơ quan phải phản hồi."
    monkeypatch.setattr("traluat.w3.grounding.repo.citable_text",
                        lambda s, eid, *args, **kw: (a if eid == "a" else b, EffectStatus.IN_FORCE))
    assert ground(FakeSession(), f"{a} {b}", D, ["a"]).abstain
    result = ground(FakeSession(), f"{a} {b}", D, ["a", "b"])
    assert not result.abstain and set(result.supported_eids) == {"a", "b"}


def test_paraphrase_requires_mapped_complete_quote_and_promote(monkeypatch):
    quote = "Doanh nghiệp phải nộp hồ sơ trong thời hạn 15 ngày làm việc."
    claim = "Doanh nghiệp cần nộp hồ sơ trong vòng 15 ngày làm việc."
    source(monkeypatch, quote)
    evidence = Citation(EID, D, claim=claim, quote=quote)
    assert ground(FakeSession(), claim, D, [evidence], nli=Verdict("hold")).abstain
    assert ground(FakeSession(), claim, D, [evidence]).abstain
    assert not ground(FakeSession(), claim, D, [evidence], nli=Verdict("promote")).abstain
    bad_span = Citation(EID, D, claim=claim, quote="phải nộp hồ sơ")
    assert ground(FakeSession(), claim, D, [bad_span], nli=Verdict("promote")).abstain
    invented = Citation(EID, D, claim=claim, quote="Nguồn không có câu này.")
    assert ground(FakeSession(), claim, D, [invented], nli=Verdict("promote")).abstain
    whitespace = Citation(EID, D, claim=claim, quote=" \n ")
    assert ground(FakeSession(), claim, D, [whitespace], nli=Verdict("promote")).abstain
    from traluat.w3 import KeywordNLIVerifier
    assert ground(FakeSession(), claim, D, [evidence], nli=KeywordNLIVerifier()).abstain


def test_exact_extraction_works_with_hold_without_trusting_generated_claim(monkeypatch):
    text = "Doanh nghiệp không được kinh doanh ngành bị cấm."
    source(monkeypatch, text)
    assert not ground(FakeSession(), text, D, [EID], nli=Verdict("hold")).abstain


class LanguageGateway(BaseLLMGateway):
    def __init__(self, *, model="m1", **kwargs):
        super().__init__(**kwargs)
        self.model = model

    def model_name(self):
        return self.model

    def _draft(self, query, chunks, prompt, as_of, node, lang):
        return f"{lang}:{self.model}", []


def test_cache_identity_includes_language_model_and_prompt_version():
    cache = {}
    gw = LanguageGateway(cache=cache)
    assert gw.generate("q", [], as_of=D, lang="vi").text == "vi:m1"
    assert gw.generate("q", [], as_of=D, lang="en").text == "en:m1"
    other = LanguageGateway(model="m2", cache=cache)
    assert other.generate("q", [], as_of=D, lang="vi").text == "vi:m2"
    before = len(cache)
    gw.prompt_version = "new-reviewed-prompt"
    gw.generate("q", [], as_of=D, lang="vi")
    assert len(cache) == before + 1
    assert ClaudeLLMGateway(model="model-a").cache_identity("answer") != \
        ClaudeLLMGateway(model="model-b").cache_identity("answer")


def test_lex_mitior_preserves_both_versions_and_requires_human(monkeypatch):
    newer = dt.date(2025, 1, 1)
    old_text, new_text = "Hình phạt là 5 năm.", "Hình phạt là 1 năm."
    def retrieve(s, query, anchor, **kwargs):
        text = old_text if anchor == D else new_text
        return [RetrievedChunk(Chunk(EID, "vi", "Điều 1", text,
                                     EffectStatus.IN_FORCE, anchor), 1.0, True)]
    monkeypatch.setattr("traluat.w3.orchestrator.retrieve", retrieve)
    class NoAutomaticDecision:
        def generate(self, *args, **kwargs):
            pytest.fail("multi-anchor applicability must not be decided by the gateway")
    ans, plan = answer_with_resolution(FakeSession(), "hành vi", gateway=NoAutomaticDecision(),
                                      question_type="hinh_su", event_date=D, today=newer)
    assert plan.lenient_fetch and ans.abstain and ans.needs_human
    assert {c["text"] for c in ans.review_context} == {old_text, new_text}
    assert {c["anchor"] for c in ans.review_context} == {D.isoformat(), newer.isoformat()}


def test_mixed_valid_and_fabricated_context_citations_are_rejected(monkeypatch):
    text = "Doanh nghiệp phải đăng ký."
    source(monkeypatch, text)
    chunk = RetrievedChunk(Chunk(EID, "vi", "Điều 1", text, EffectStatus.IN_FORCE, D), 1.0, True)
    monkeypatch.setattr("traluat.w3.orchestrator.retrieve", lambda *a, **kw: [chunk])
    class Rogue:
        def generate(self, *args, **kwargs):
            return LLMResult(text, [Citation(EID), Citation("invented")])
    ans = answer_question(FakeSession(), "q", as_of=D, gateway=Rogue())
    assert ans.abstain and ans.reason == "citation_outside_context"
