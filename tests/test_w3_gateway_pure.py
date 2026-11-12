"""W3 gateway — untrusted-wrap · guard tenant · cache · NotConfigured (pure)."""

import datetime as dt
from dataclasses import dataclass

import pytest

from traluat.w3 import ClaudeLLMGateway, EchoLLMGateway, NotConfigured, wrap_untrusted
from traluat.w3.gateway import TenantLeak

D = dt.date
_DEFAULT_AS_OF = D(2022, 1, 1)


@dataclass
class FakeChunk:
    unit_eid: str
    span_text: str
    as_of: dt.date = _DEFAULT_AS_OF
    tenant_id: str | None = None


def test_wrap_untrusted_has_boundary_and_provenance():
    out = wrap_untrusted([FakeChunk("nd99__dieu_1", "Nội dung điều 1.")])
    assert "<<DATA" in out and "source_eid=nd99__dieu_1" in out and "<<END" in out
    assert "Nội dung điều 1." in out


def test_tenant_guard_blocks_cross_tenant():
    gw = EchoLLMGateway()
    chunks = [FakeChunk("x__dieu_1", "abc", tenant_id="t_A")]
    with pytest.raises(TenantLeak):
        gw.generate("hỏi", chunks, as_of=D(2022, 1, 1), tenant_id="t_B")


def test_cache_and_audit():
    gw = EchoLLMGateway()
    chunks = [FakeChunk("x__dieu_1", "abc")]
    r1 = gw.generate("hỏi", chunks, as_of=D(2022, 1, 1))
    r2 = gw.generate("hỏi", chunks, as_of=D(2022, 1, 1))
    assert r1 is r2                      # cache content-hash → cùng object
    assert len(gw.audit_log) == 1        # lần 2 hit cache, không audit lại
    assert r1.ai_label is True and r1.citations[0].unit_eid == "x__dieu_1"


def test_claude_gateway_not_configured():
    # chưa cài 'anthropic' / chưa có key → raise rõ ràng, KHÔNG giả vờ trả lời
    gw = ClaudeLLMGateway()
    with pytest.raises(NotConfigured):
        gw.generate("hỏi", [FakeChunk("x__dieu_1", "abc")], as_of=D(2022, 1, 1))
