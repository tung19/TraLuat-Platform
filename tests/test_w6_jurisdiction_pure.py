"""W6 JurisdictionPack — rank/role/load (pure)."""

import datetime as dt

import pytest

from traluat.w6 import VN_PACK, JurisdictionPack, get_pack, load_pack, register_pack

D = dt.date


def test_vn_pack_rank():
    assert VN_PACK.rank_of("luat", D(2026, 1, 1)) == 90
    assert VN_PACK.rank_of("thong_tu", D(2026, 1, 1)) == 50
    assert VN_PACK.rank_of("quyet_dinh", D(2026, 1, 1)) is None            # mơ hồ, thiếu cơ quan
    assert VN_PACK.rank_of("quyet_dinh", D(2026, 1, 1), "thu_tuong") == 65  # có cơ quan


def test_registry():
    assert get_pack("vn") is VN_PACK
    with pytest.raises(KeyError):
        get_pack("xx")
    p = JurisdictionPack(code="th", lang="th", rank_table={"act": 90})
    register_pack(p)
    assert get_pack("th").rank_of("act", D(2026, 1, 1)) == 90


def test_load_pack_from_config():
    pack = load_pack({
        "code": "demo", "lang": "en",
        "rank_table": {"statute": "90", "regulation": "50"},
        "roles": [{"name": "counsel", "query_focus": "rights"}],
        "ambiguous_types": ["order"],
        "authority_key": {"order|pm": "pm_order"},
    })
    assert pack.rank_of("statute", D(2026, 1, 1)) == 90
    assert pack.roles[0].name == "counsel"
    assert pack.ambiguous_types == {"order"}
    assert pack.authority_key[("order", "pm")] == "pm_order"
