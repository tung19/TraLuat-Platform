"""Observability tối thiểu (W5 §4) — counter in-process + render Prometheus text.

Theo dõi theo tenant: request · abstain · egress-deny · route-destination. OTel/
Prometheus backend thật = scrape /metrics (cùng format). Không nội dung, chỉ metric.
"""

from __future__ import annotations

from collections import defaultdict


class Metrics:
    def __init__(self) -> None:
        self._c: dict[tuple, int] = defaultdict(int)

    def inc(self, name: str, **labels: str) -> None:
        self._c[(name, tuple(sorted(labels.items())))] += 1

    def value(self, name: str, **labels: str) -> int:
        return self._c.get((name, tuple(sorted(labels.items()))), 0)

    def render(self) -> str:
        lines = []
        for (name, labels), v in sorted(self._c.items()):
            if labels:
                lbl = ",".join(f'{k}="{val}"' for k, val in labels)
                lines.append(f"{name}{{{lbl}}} {v}")
            else:
                lines.append(f"{name} {v}")
        return "\n".join(lines) + "\n"
