"""WP5 · Observability — OpenTelemetry tracing (span API/service/gateway).

OTel là **tuỳ chọn** (extra `obs`): nếu SDK chưa cài → `span()` no-op, hệ vẫn chạy
(metrics Prometheus + trace_id audit vẫn đủ quan sát tối thiểu). Có SDK:
`setup_tracing()` dựng TracerProvider (+ OTLP exporter nếu `OTEL_EXPORTER_OTLP_ENDPOINT`),
và `span(name, **attrs)` là context-manager tạo span con, gắn trace_id W5 làm attribute
để nối Prometheus ↔ Jaeger. Không đụng lõi — gọi `span()` ở biên (API/service).
"""

from __future__ import annotations

import os
from contextlib import contextmanager

try:  # SDK optional — chỉ cần khi bật tracing thật
    from opentelemetry import trace as _ot_trace
    _HAS_OTEL = True
except Exception:  # noqa: BLE001
    _ot_trace = None
    _HAS_OTEL = False

_PROVIDER = None  # giữ provider đã dựng (idempotent)


def tracing_available() -> bool:
    return _HAS_OTEL


def setup_tracing(service_name: str = "traluat", *, exporter=None):
    """Dựng TracerProvider 1 lần. `exporter` (vd InMemorySpanExporter cho test) ưu tiên;
    nếu không, dùng OTLP khi có env `OTEL_EXPORTER_OTLP_ENDPOINT`. Trả provider (hoặc None
    nếu OTel chưa cài)."""
    global _PROVIDER
    if not _HAS_OTEL:
        return None
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(exporter))     # test: flush ngay
    elif os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    _ot_trace.set_tracer_provider(provider)
    _PROVIDER = provider
    return provider


@contextmanager
def span(name: str, *, trace_id: str | None = None, **attrs):
    """Mở span con quanh một đoạn công việc (biên API/service/gateway). No-op nếu chưa
    cài/khởi tạo OTel. Gắn `trace_id` (W5 audit) + attrs để nối các backend quan sát."""
    if not _HAS_OTEL:
        yield None
        return
    tracer = _ot_trace.get_tracer("traluat")
    with tracer.start_as_current_span(name) as sp:
        if trace_id:
            sp.set_attribute("traluat.trace_id", trace_id)
        for k, v in attrs.items():
            if v is not None:
                sp.set_attribute(k, v)
        yield sp
