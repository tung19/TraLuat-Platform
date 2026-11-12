"""W5 lõi bảo mật — tenancy · egress fail-closed/R2 · audit write-ahead (pure)."""

import pytest

from traluat.w5 import (
    AuditLog,
    DataClass,
    EgressPolicy,
    LLMDestination,
    MissingTenant,
    TenantContext,
    require_role,
)


def test_tenant_context_requires_id():
    with pytest.raises(MissingTenant):
        TenantContext("")
    with pytest.raises(ValueError):
        TenantContext("t1", role="hacker")


def test_require_role():
    ctx = TenantContext("t1", role="viewer")
    require_role(ctx, "viewer", "lawyer")           # ok
    with pytest.raises(PermissionError):
        require_role(ctx, "owner")


def test_egress_classify_fail_closed():
    e = EgressPolicy()
    assert e.classify(["public_kb"]) == DataClass.PUBLIC_KB
    assert e.classify(["tenant:x", "public_kb"]) == DataClass.CLIENT_SENSITIVE
    assert e.classify([]) == DataClass.CLIENT_SENSITIVE   # rỗng → fail-closed


def test_egress_r2_never_failover_sensitive():
    e = EgressPolicy()
    up = e.decide(DataClass.CLIENT_SENSITIVE, local_available=True)
    assert up.destination == LLMDestination.LOCAL
    down = e.decide(DataClass.CLIENT_SENSITIVE, local_available=False)
    assert down.destination == LLMDestination.DENY       # ★ KHÔNG sang Claude
    assert down.destination != LLMDestination.CLAUDE
    pub = e.decide(DataClass.PUBLIC_KB, local_available=True)
    assert pub.destination == LLMDestination.CLAUDE       # dữ liệu công → được ra ngoài


def test_public_falls_back_local_when_claude_unavailable():
    # review-fix #1: public + chưa cấu hình claude_gateway → LOCAL, KHÔNG deny oan
    e = EgressPolicy()
    d = e.decide(DataClass.PUBLIC_KB, local_available=True, claude_available=False)
    assert d.destination == LLMDestination.LOCAL


def test_metrics_counter():
    from traluat.w5.metrics import Metrics
    m = Metrics()
    m.inc("req", tenant="a"); m.inc("req", tenant="a"); m.inc("req", tenant="b")
    assert m.value("req", tenant="a") == 2 and m.value("req", tenant="b") == 1
    assert 'req{tenant="a"} 2' in m.render()


def test_audit_write_ahead_append_only():
    log = AuditLog()
    intent = log.record_intent(
        tenant_id="t1", actor="api", action="analyze", resource="case",
        trace_id="TR", data_class="client_sensitive", residency="vn",
        llm_destination="local")
    log.confirm(intent, "done")
    rows = log.by_trace("TR")
    assert [r.phase for r in rows] == ["intent", "done"]  # intent ghi TRƯỚC, giữ nguyên
    assert rows[0].llm_destination == "local"
