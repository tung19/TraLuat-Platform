#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate meta.json của đội data theo schemas/meta.schema.json.

Dùng:
    python scripts/validate_meta.py sample_data/            # validate cả thư mục *.json
    python scripts/validate_meta.py path/to/one.json        # validate một file

Cần: pip install jsonschema
Trả exit code 0 nếu tất cả pass, 1 nếu có file fail (tiện cho CI / đội data tự kiểm).
"""
import json
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print("Thiếu thư viện: pip install jsonschema", file=sys.stderr)
    sys.exit(2)

_DATE_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _semantic_checks(data, path="(gốc)"):
    """Chaos-fix S2+S3: schema pattern chỉ check HÌNH DẠNG số — thêm kiểm LỊCH THẬT + NFC.
    (vd '2071-13-45' / '2021-99-99' từng PASS; OCR lật 2021→2071 lọt.)"""
    errs = []
    this_year = date.today().year

    def walk(node, loc):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{loc}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{loc}/{i}")
        elif isinstance(node, str):
            # NFC (S3): dấu tiếng Việt phải chuẩn hoá NFC
            if unicodedata.normalize("NFC", node) != node:
                errs.append(f"[{loc}] chuỗi KHÔNG ở dạng NFC (chuẩn hoá trước khi gửi)")
            # Ngày lịch thật (S2)
            if _DATE_SHAPE.match(node):
                try:
                    d = datetime.strptime(node, "%Y-%m-%d").date()
                except ValueError:
                    errs.append(f"[{loc}] '{node}' đúng hình dạng nhưng KHÔNG phải ngày lịch hợp lệ")
                    return
                if not (1945 <= d.year <= this_year + 5):
                    errs.append(f"[{loc}] năm {d.year} ngoài khoảng hợp lý [1945..{this_year+5}] (nghi OCR sai)")

    walk(data, path)
    return errs

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "meta.schema.json"


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_file(validator, path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"JSON không parse được: {e}"]
    errs = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    out = []
    for e in errs:
        loc = "/".join(str(p) for p in e.path) or "(gốc)"
        out.append(f"[{loc}] {e.message}")
    out.extend(_semantic_checks(data))   # ★ S2 (ngày lịch thật) + S3 (NFC) — schema không bắt được
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    target = Path(argv[1])
    files = sorted(target.glob("*.json")) if target.is_dir() else [target]
    files = [f for f in files if f.name != "meta.schema.json"]
    if not files:
        print("Không tìm thấy file .json nào.")
        return 2

    validator = Draft202012Validator(load_schema())
    n_pass = n_fail = 0
    for f in files:
        errs = validate_file(validator, f)
        if errs:
            n_fail += 1
            print(f"✗ FAIL  {f.name}")
            for msg in errs:
                print(f"        - {msg}")
        else:
            n_pass += 1
            print(f"✓ PASS  {f.name}")
    print(f"\n{n_pass} pass · {n_fail} fail · {len(files)} file")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
