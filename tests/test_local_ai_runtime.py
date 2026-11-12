"""Local transport boundary and output contract; no model downloads/network."""
import datetime as dt
import json

import httpx
import pytest

from traluat.w2.bitemporal import EffectStatus
from traluat.w3.chunker import Chunk
from traluat.w3.local_gateway import LocalLLMGateway, LocalModelError
from traluat.w3.retrieval import RetrievedChunk
from traluat.w5.ai_runtime import load_runtime_ai

D = dt.date(2024, 1, 1)
TEXT = "Doanh nghiệp phải nộp hồ sơ trong 15 ngày làm việc."
CHUNKS = [RetrievedChunk(Chunk("demo__dieu_1", "vi", "Dữ liệu giả", TEXT,
                               EffectStatus.IN_FORCE, D), 1.0, True)]


def gateway(handler, **kwargs):
    return LocalLLMGateway(base_url="http://127.0.0.1:11434/v1", model="test-local",
                           transport=httpx.MockTransport(handler), **kwargs)


def completion(content=None, finish="stop"):
    data = content if content is not None else json.dumps({
        "text": TEXT, "citations": [{"unit_eid": "demo__dieu_1", "claim": TEXT, "quote": TEXT}]})
    return httpx.Response(200, json={"choices": [{"finish_reason": finish,
                                                 "message": {"content": data}}]})


def test_local_request_contract_and_claim_quote_preserved():
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"model_info": {"general.architecture": "llama"}})
        body = json.loads(request.content)
        assert body["model"] == "test-local" and body["stream"] is False
        assert body["response_format"]["json_schema"]["strict"] is True
        assert TEXT in body["messages"][1]["content"]
        return completion()
    model = gateway(handler)
    for _ in range(2):
        answer = model.generate("hồ sơ?", CHUNKS, as_of=D, tenant_id="one")
        assert answer.citations[0].claim == TEXT == answer.citations[0].quote
        assert answer.citations[0].anchor == D
    assert len([r for r in requests if r.url.path.endswith("completions")]) == 2
    assert not model._cache


@pytest.mark.parametrize("metadata", [{}, {"model_info": {"x": 1}, "remote_host": "cloud"},
                                      {"model_info": {"x": 1}, "remote_model": "cloud-model"}])
def test_cloud_or_unknown_model_never_receives_client_context(metadata):
    def handler(request):
        assert request.url.path == "/api/show"
        assert "private client text" not in request.content.decode()
        return httpx.Response(200, json=metadata)
    with pytest.raises(LocalModelError, match="local_model_unavailable"):
        gateway(handler).generate("private client text", CHUNKS, as_of=D)


@pytest.mark.parametrize("url", ["https://api.openai.com/v1", "https://ollama.com/v1",
                                 "http://127.0.0.1/v1?redirect=1", "http://user:pass@localhost/v1"])
def test_nonlocal_or_ambiguous_endpoint_rejected(url):
    with pytest.raises(ValueError):
        LocalLLMGateway(base_url=url, model="test")


@pytest.mark.parametrize(("content", "finish"), [
    ("not json", "stop"), ('{"text": "partial", "citations": []}', "length"),
    ('{"text": "x", "citations": [{"unit_eid": "x"}]}', "stop"),
    ('{"text": 17, "citations": []}', "stop"),
])
def test_malformed_or_truncated_output_cannot_be_an_answer(content, finish):
    def handler(request):
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"model_info": {"x": 1}})
        return completion(content, finish)
    with pytest.raises(LocalModelError, match="invalid_model_output"):
        gateway(handler).generate("q", CHUNKS, as_of=D)


def test_redirects_and_transport_failures_fail_closed():
    model = gateway(lambda r: httpx.Response(307, headers={"Location": "https://example.com"}))
    assert not model.healthy()
    def timeout(request):
        raise httpx.ReadTimeout("synthetic private provider message", request=request)
    with pytest.raises(LocalModelError, match="^local_model_unavailable$"):
        gateway(timeout).generate("q", CHUNKS, as_of=D)


def test_runtime_modes_do_not_silently_substitute_echo():
    assert not load_runtime_ai({}).gateway.healthy()
    assert load_runtime_ai({"TRALUAT_AI_MODE": "demo"}).gateway.model_name() == "echo-stub"
    with pytest.raises(ValueError):
        load_runtime_ai({"TRALUAT_AI_MODE": "local"})  # missing model, before any downloads


def test_factory_injects_same_models_once(monkeypatch):
    from traluat.w3 import embed_bge, nli_xnli
    seen = []
    class Embed:
        dim = 1024
        def __init__(self, **kwargs):
            seen.append(("embed", kwargs))
    class NLI:
        def __init__(self, **kwargs):
            seen.append(("nli", kwargs))
    monkeypatch.setattr(embed_bge, "BgeM3Embedder", Embed)
    monkeypatch.setattr(nli_xnli, "XNLIVerifier", NLI)
    runtime = load_runtime_ai({"TRALUAT_AI_MODE": "local", "TRALUAT_LOCAL_MODEL": "test-local"})
    assert isinstance(runtime.retriever.embedder, Embed) and isinstance(runtime.nli, NLI)
    assert len(seen) == 2 and all(kwargs["local_files_only"] for _, kwargs in seen)
@pytest.mark.parametrize("action,target", [
    ("analyze", "traluat.w4.ReasoningEngine.analyze"),
    ("draft", "traluat.w6.PetitionDraftService.draft"),
    ("advise", "traluat.w6.ComplianceAdvisoryService.advise"),
])
def test_workflow_model_failure_abstains_and_audits(monkeypatch, action, target):
    from traluat.w3.gateway import EchoLLMGateway
    from traluat.w4 import CaseInput
    from traluat.w5 import LegalService, TenantContext

    def fail(*args, **kwargs):
        raise LocalModelError("invalid_model_output")
    monkeypatch.setattr(target, fail)
    service = LegalService(None, local_gateway=EchoLLMGateway())
    ctx = TenantContext("synthetic-tenant", role="lawyer")
    if action == "analyze":
        result = service.analyze(CaseInput(facts="synthetic"), dt.date(2024, 1, 1), ctx)
        trace = result.trace_id
        assert not result.answered and result.adjudication is None
    elif action == "draft":
        result, trace = service.draft("synthetic", "synthetic", dt.date(2024, 1, 1), ctx)
        assert result.abstain and result.text == ""
    else:
        result, trace = service.advise("synthetic", dt.date(2024, 1, 1), ctx)
        assert result.abstain and result.advice == ""
    assert result.reason == "invalid_model_output"
    assert [row.phase for row in service.audit.by_trace(trace)] == ["intent", "failed"]
