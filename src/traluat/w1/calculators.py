"""FR-35 Calculator registry — tiện ích tính RULE, HIỆU-LỰC + CÓ-NGUỒN-LUẬT.

Khác TVPL: mỗi kết quả kèm `source_eid` (điều luật căn cứ) + giá trị@as_of (bitemporal).
Mỗi calc = hàm thuần trên `lookup_reference` (bảng tham chiếu đội data đẩy). Route:
`classify_tier`→RULE → gọi đây (KHÔNG LLM). Đăng ký qua @calculator.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from .reference import lookup_reference

_REGISTRY: dict[str, Callable] = {}


def calculator(name: str):
    def deco(fn):
        _REGISTRY[name] = fn
        return fn
    return deco


def available() -> list[str]:
    return sorted(_REGISTRY)


@dataclass
class CalcResult:
    name: str
    value: dict               # kết quả (số + đơn vị)
    source_eid: str | None    # điều luật căn cứ (moat: có-nguồn-luật)
    as_of: dt.date
    basis: str = ""           # giải thích ngắn (dataset + key)


def run(session: Session, name: str, params: dict, as_of: dt.date) -> CalcResult:
    if name not in _REGISTRY:
        raise KeyError(f"calculator không có: {name} (có: {available()})")
    return _REGISTRY[name](session, params, as_of)


def _lookup(session, dataset, key, as_of) -> tuple[dict, str | None]:
    rv = lookup_reference(session, dataset, key, as_of)
    if rv is None:
        raise LookupError(f"không có dữ liệu {dataset}/{key}@{as_of}")
    return rv.value, rv.source_eid


# ── Các calculator (tra bảng hiệu-lực; số học đơn giản) ──────────────────────
@calculator("muc_phat")
def _muc_phat(session, params, as_of) -> CalcResult:
    """Mức phạt cho một hành vi tại as_of."""
    val, src = _lookup(session, "muc_phat", params["hanh_vi"], as_of)
    return CalcResult("muc_phat", val, src, as_of, f"muc_phat/{params['hanh_vi']}")


@calculator("thue_tncn")
def _thue_tncn(session, params, as_of) -> CalcResult:
    """Thuế TNCN: thu nhập tính thuế × thuế suất bậc (bảng hiệu-lực)."""
    income = float(params["thu_nhap"])
    rate, src = _lookup(session, "thue_suat_tncn", params.get("bac", "bac1"), as_of)
    tax = income * float(rate["rate"])
    return CalcResult("thue_tncn", {"thue": round(tax), "rate": rate["rate"]}, src, as_of,
                      f"thue_suat_tncn/{params.get('bac', 'bac1')}")


@calculator("luong_toi_thieu")
def _luong(session, params, as_of) -> CalcResult:
    """Lương tối thiểu vùng tại as_of."""
    val, src = _lookup(session, "luong_toi_thieu", params["vung"], as_of)
    return CalcResult("luong_toi_thieu", val, src, as_of, f"luong_toi_thieu/{params['vung']}")


@calculator("le_phi")
def _le_phi(session, params, as_of) -> CalcResult:
    val, src = _lookup(session, "le_phi", params["loai"], as_of)
    return CalcResult("le_phi", val, src, as_of, f"le_phi/{params['loai']}")
