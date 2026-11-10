"""FR-38 · biểu mẫu có cấu trúc + validation (thuần, không DB)."""

from __future__ import annotations

from traluat.w1.forms import FormField, fill_form, validate_form

_SLOTS = [
    {"name": "ho_ten", "label": "Họ tên", "type": "text", "required": True},
    {"name": "ngay_sinh", "label": "Ngày sinh", "type": "date", "required": True},
    {"name": "so_tien", "label": "Số tiền", "type": "number"},
    {"name": "loai", "label": "Loại", "type": "choice", "options": ["A", "B"]},
    {"name": "cccd", "label": "CCCD", "type": "text", "pattern": r"\d{12}"},
]


def test_valid_form_passes_and_fills():
    vals = {"ho_ten": "Nguyễn Văn A", "ngay_sinh": "1990-05-01", "so_tien": "1000000",
            "loai": "A", "cccd": "012345678901"}
    assert validate_form(_SLOTS, vals) == []
    out, errs = fill_form("Tôi {ho_ten}, sinh {ngay_sinh}, nộp {so_tien}đ.", _SLOTS, vals)
    assert errs == [] and out == "Tôi Nguyễn Văn A, sinh 1990-05-01, nộp 1000000đ."


def test_required_missing():
    errs = validate_form(_SLOTS, {"so_tien": "100"})
    assert any("Họ tên" in e for e in errs) and any("Ngày sinh" in e for e in errs)


def test_type_and_choice_and_pattern_errors():
    errs = validate_form(_SLOTS, {"ho_ten": "X", "ngay_sinh": "01/01/1990",
                                  "so_tien": "nhiều", "loai": "Z", "cccd": "123"})
    assert any("Ngày sinh" in e for e in errs)      # date sai
    assert any("Số tiền" in e for e in errs)        # không phải số
    assert any("Loại" in e for e in errs)           # ngoài options
    assert any("CCCD" in e for e in errs)           # sai pattern


def test_fill_blocked_when_invalid():
    out, errs = fill_form("{ho_ten}", _SLOTS, {})   # thiếu bắt buộc
    assert errs and out == "{ho_ten}"               # KHÔNG điền bừa


def test_string_slot_backward_compat():
    assert FormField.parse("ten").name == "ten"
    assert validate_form(["ten"], {"ten": "x"}) == []    # slot chuỗi = text không-bắt-buộc
