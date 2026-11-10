"""JurisdictionPack — cấu hình vùng tài phán, cắm vào engine (portability).

Thay thế việc engine đọc trực tiếp hằng số VN: thang bậc rank, vai tranh biện,
doc_type mơ hồ đều nằm trong pack. Nước thứ 2 = pack mới (rank/role/lang khác),
engine không đổi. `rank_of` cùng chữ ký `legal_rule_base.rank_of` để bơm vào
`resolve_conflict(rank_fn=...)`.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from ..core import legal_rule_base as lrb
from ..w4.multi_role import DEFAULT_ROLES, RoleConfig


@dataclass
class JurisdictionPack:
    code: str                                      # "vn", "th", ...
    lang: str = "vi"
    rank_table: dict[str, int] = field(default_factory=dict)       # doc_type → rank
    roles: list[RoleConfig] = field(default_factory=list)          # vai tranh biện
    ambiguous_types: set[str] = field(default_factory=set)         # cần authority để định rank
    authority_key: dict[tuple[str, str], str] = field(default_factory=dict)

    def rank_of(self, doc_type: str, as_of: dt.date, authority_hint: str | None = None) -> int | None:
        if doc_type in self.ambiguous_types:
            key = self.authority_key.get((doc_type, authority_hint))
            return self.rank_table.get(key) if key else None
        return self.rank_table.get(doc_type)


# Pack VN mặc định — dựng từ legal_rule_base hiện hành (PROVISIONAL như lrb).
VN_PACK = JurisdictionPack(
    code="vn", lang="vi",
    rank_table=dict(lrb._RANK_CURRENT),
    roles=list(DEFAULT_ROLES),
    ambiguous_types=set(lrb._AMBIGUOUS),
    authority_key=dict(lrb._AUTHORITY_KEY),
)

_REGISTRY: dict[str, JurisdictionPack] = {"vn": VN_PACK}


def register_pack(pack: JurisdictionPack) -> None:
    _REGISTRY[pack.code] = pack


def get_pack(code: str = "vn") -> JurisdictionPack:
    if code not in _REGISTRY:
        raise KeyError(f"chưa đăng ký JurisdictionPack: {code}")
    return _REGISTRY[code]


def load_pack(data: dict) -> JurisdictionPack:
    """Nạp pack từ config (JSON). authority_key key dạng 'doc_type|authority'."""
    roles = [RoleConfig(**r) if isinstance(r, dict) else RoleConfig(r)
             for r in data.get("roles", [])]
    akey = {tuple(k.split("|", 1)): v for k, v in data.get("authority_key", {}).items()}
    return JurisdictionPack(
        code=data["code"], lang=data.get("lang", "vi"),
        rank_table={k: int(v) for k, v in data.get("rank_table", {}).items()},
        roles=roles, ambiguous_types=set(data.get("ambiguous_types", [])),
        authority_key=akey,
    )
