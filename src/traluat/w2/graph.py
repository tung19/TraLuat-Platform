"""GraphStore port (ADR-0001) — seam để đổi engine đồ thị không đụng Researcher/API.

Mặc định PostgresGraphStore (recursive CTE, cùng SoR + snapshot bitemporal). Khi
chạm trigger (GDS/deep-path/GraphRAG — ADR §6): cắm AGEGraphStore (Cypher trong
Postgres, ưu tiên) hoặc Neo4jGraphStore (projection read-only + cột-mốc consistency).
Đổi chỉ là impl của port — y hệt bge-m3/XNLI/VietOCR đã cắm.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from . import repo


@runtime_checkable
class GraphStore(Protocol):
    def multihop(self, start_eid: str, rel_types: list[str], max_hops: int = 3,
                 as_of: dt.date | None = None) -> list[str]: ...
    def neighborhood(self, eid: str, as_of: dt.date | None = None,
                     rel_types: list[str] | None = None, max_hops: int = 1) -> dict: ...


class PostgresGraphStore:
    """Impl mặc định — norm_relation + recursive CTE. Một SoR, lọc hiệu lực @as_of."""
    def __init__(self, session: Session) -> None:
        self.s = session

    def multihop(self, start_eid, rel_types, max_hops=3, as_of=None):
        return repo.multihop(self.s, start_eid, rel_types, max_hops=max_hops, as_of=as_of)

    def neighborhood(self, eid, as_of=None, rel_types=None, max_hops=1):
        return repo.neighborhood(self.s, eid, as_of, rel_types, max_hops)
