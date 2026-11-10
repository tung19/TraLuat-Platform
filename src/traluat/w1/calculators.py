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


@calculator("thue_gtgt")
def _thue_gtgt(session, params, as_of) -> CalcResult:
    """35.2 — thuế GTGT: giá × thuế-suất@T (neo NĐ/TT). params={gia, loai}."""
    gia = float(params["gia"])
    rate, src = _lookup(session, "thue_gtgt", params.get("loai", "chung_10"), as_of)
    r = float(rate["rate"])
    thue = round(gia * r)
    return CalcResult("thue_gtgt",
                      {"thue": thue, "gia_sau_thue": round(gia + thue), "rate": r},
                      src, as_of, f"thue_gtgt/{params.get('loai', 'chung_10')}")


@calculator("lam_them_gio")
def _lam_them_gio(session, params, as_of) -> CalcResult:
    """35.9 — tiền làm thêm giờ = lương-giờ × hệ-số(loại ngày)@T × số giờ (neo BLLĐ).
    params={luong_gio, so_gio, loai_ngay(ngay_thuong|ngay_nghi|ngay_le)}."""
    luong_gio = float(params["luong_gio"])
    so_gio = float(params["so_gio"])
    loai = params.get("loai_ngay", "ngay_thuong")
    rate, src = _lookup(session, "lam_them_rate", loai, as_of)
    he_so = float(rate["rate"])
    tien = round(luong_gio * he_so * so_gio)
    return CalcResult("lam_them_gio", {"tien": tien, "he_so": he_so}, src, as_of,
                      f"lam_them_rate/{loai}")


def _progressive(taxable: float, brackets: list) -> float:
    """Thuế luỹ tiến từng phần. brackets=[[upper, rate],…] tăng dần; upper=None=∞."""
    tax = 0.0
    lower = 0.0
    for upper, rate in brackets:
        cap = taxable if (upper is None or taxable < upper) else float(upper)
        if cap > lower:
            tax += (cap - lower) * float(rate)
        if upper is None or taxable <= upper:
            break
        lower = float(upper)
    return tax


@calculator("gross_net")
def _gross_net(session, params, as_of) -> CalcResult:
    """35.6 — Gross→Net lương: trừ BH bắt buộc + TNCN luỹ-tiến sau giảm-trừ, theo
    tỷ-lệ/biểu/giảm-trừ HIỆU-LỰC@T (neo luật). params={gross, nguoi_phu_thuoc?}."""
    gross = float(params["gross"])
    npt = int(params.get("nguoi_phu_thuoc", 0))

    bh, _ = _lookup(session, "ty_le_bh", "nld", as_of)             # tổng BH phía NLĐ
    gt, _ = _lookup(session, "giam_tru_gia_canh", "chuan", as_of)  # bản thân + phụ thuộc
    bieu, src = _lookup(session, "bieu_thue_tncn", "thang", as_of)  # biểu luỹ tiến (neo luật)

    insurance = round(gross * float(bh["rate"]))
    giam_tru = float(gt["ban_than"]) + npt * float(gt["phu_thuoc"])
    taxable = max(0.0, gross - insurance - giam_tru)
    tax = round(_progressive(taxable, bieu["brackets"]))
    net = round(gross - insurance - tax)
    return CalcResult("gross_net",
                      {"net": net, "bao_hiem": insurance, "thue_tncn": tax,
                       "thu_nhap_tinh_thue": round(taxable)},
                      src, as_of, "bieu_thue_tncn/thang (+ty_le_bh,giam_tru)")
