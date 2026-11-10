"""FR-38 · Biểu mẫu có CẤU TRÚC + VALIDATION — nối kho mẫu (Template, FR-34).

Template.slots nâng từ list-tên thành list field-def: {name, label, type, required,
pattern?, options?}. `validate_form` kiểm (bắt buộc / kiểu / regex / lựa-chọn) → danh
sách lỗi; `fill_form` validate rồi thế `{name}` vào body. Tất định, không LLM.
Tương thích ngược: slot là chuỗi → field text tên theo chuỗi.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

_TYPES = {"text", "number", "date", "choice"}


@dataclass
class FormField:
    name: str
    label: str = ""
    type: str = "text"
    required: bool = False
    pattern: str | None = None
    options: list | None = None

    @classmethod
    def parse(cls, slot) -> FormField:
        if isinstance(slot, str):
            return cls(name=slot, label=slot)
        f = cls(name=slot["name"], label=slot.get("label", slot["name"]),
                type=slot.get("type", "text"), required=bool(slot.get("required", False)),
                pattern=slot.get("pattern"), options=slot.get("options"))
        if f.type not in _TYPES:
            raise ValueError(f"type không hợp lệ: {f.type}")
        return f


def _fields(slots) -> list[FormField]:
    return [FormField.parse(s) for s in (slots or [])]


def _check(f: FormField, raw) -> str | None:
    """None nếu hợp lệ, else thông báo lỗi (1 field)."""
    missing = raw is None or (isinstance(raw, str) and raw.strip() == "")
    if missing:
        return f"{f.label}: bắt buộc" if f.required else None
    v = str(raw)
    if f.type == "number":
        try:
            float(v.replace(",", ""))
        except ValueError:
            return f"{f.label}: phải là số"
    elif f.type == "date":
        try:
            dt.date.fromisoformat(v)
        except ValueError:
            return f"{f.label}: ngày sai (YYYY-MM-DD)"
    elif f.type == "choice" and f.options is not None and v not in [str(o) for o in f.options]:
        return f"{f.label}: phải thuộc {f.options}"
    if f.pattern and not re.fullmatch(f.pattern, v):
        return f"{f.label}: sai định dạng"
    return None


def validate_form(slots, values: dict) -> list[str]:
    """Trả danh sách lỗi (rỗng = hợp lệ)."""
    errs = []
    for f in _fields(slots):
        e = _check(f, values.get(f.name))
        if e:
            errs.append(e)
    return errs


def fill_form(body: str, slots, values: dict) -> tuple[str, list[str]]:
    """Validate rồi thế `{name}`→giá trị. Có lỗi → (body gốc, errors), KHÔNG điền bừa."""
    errs = validate_form(slots, values)
    if errs:
        return body, errs
    out = body
    for f in _fields(slots):
        out = out.replace("{" + f.name + "}", str(values.get(f.name, "")))
    return out, []
