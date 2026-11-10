"""WP5 · Observability (OTel span) + Security (HSM/cloud KMS port) — thuần, không PG."""

from __future__ import annotations

import pytest

from traluat.w5.crypto import (
    CryptoShredded,
    RemoteKMSProvider,
    SoftwareKMS,
    TenantCrypto,
)


def test_span_recorded_in_memory():
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from traluat.w5 import tracing
    exp = InMemorySpanExporter()
    tracing.setup_tracing("traluat-test", exporter=exp)

    with tracing.span("unit.work", trace_id="abc123", **{"traluat.destination": "local"}):
        pass

    spans = exp.get_finished_spans()
    assert any(s.name == "unit.work" for s in spans)
    s = next(s for s in spans if s.name == "unit.work")
    assert s.attributes["traluat.trace_id"] == "abc123"
    assert s.attributes["traluat.destination"] == "local"


def test_span_noop_safe_without_setup():
    # span() không được ném dù OTel chưa khởi tạo provider (biên gọi luôn an toàn)
    from traluat.w5.tracing import span
    with span("x", trace_id="t"):
        pass


def test_remote_kms_roundtrip_via_callables():
    # HSM/cloud KMS giả lập bằng 2 callable khả-nghịch → wrap/unwrap DEK roundtrip
    calls = {"wrap": 0, "unwrap": 0}

    def wrap(dek: bytes) -> bytes:
        calls["wrap"] += 1
        return b"KMS:" + dek[::-1]

    def unwrap(wrapped: bytes) -> bytes:
        calls["unwrap"] += 1
        assert wrapped.startswith(b"KMS:")
        return wrapped[4:][::-1]

    kms = RemoteKMSProvider(wrap, unwrap)
    tc = TenantCrypto(kms)
    ct = tc.encrypt("t-1", "bí mật khách hàng")
    assert tc.decrypt("t-1", ct) == "bí mật khách hàng"
    assert calls["wrap"] == 1           # DEK bọc 1 lần khi sinh
    assert calls["unwrap"] >= 1         # mở DEK để giải


def test_remote_kms_interchangeable_with_software_kms():
    # Cùng port KMSProvider → thay SoftwareKMS↔RemoteKMS không đụng TenantCrypto
    for kms in (SoftwareKMS(), RemoteKMSProvider(lambda d: b">" + d, lambda w: w[1:])):
        tc = TenantCrypto(kms)
        ct = tc.encrypt("t", "x")
        assert tc.decrypt("t", ct) == "x"
        tc.crypto_shred("t")
        with pytest.raises(CryptoShredded):
            tc.decrypt("t", ct)
