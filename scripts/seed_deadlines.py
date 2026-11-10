"""Seed thời hiệu tố tụng (FR-35.13) + ngày lễ (FR-35.14) vào reference_value.

Idempotent (upsert theo khoá). Giá trị thời hạn là **đại diện, cần chuyên gia xác
nhận** — đúng-sai số liệu thuộc đội data; moat là CƠ CHẾ (hiệu-lực-aware + neo điều).
    uv run python scripts/seed_deadlines.py
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from sqlalchemy.orm import Session

from traluat.w1.reference import RefRow, upsert_reference
from traluat.w2.db import make_engine

ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"


def seed() -> tuple[int, int]:
    with Session(make_engine(), future=True) as s:
        dl = [json.loads(x) for x in (ROOT / "deadlines.jsonl").read_text(
            encoding="utf-8").splitlines() if x.strip()]
        upsert_reference(s, "thoi_hieu", [
            RefRow(r["kind"], {"value": r["value"], "unit": r["unit"], "note": r.get("note")},
                   dt.date.fromisoformat(r["valid_from"]), None, r.get("source_eid"))
            for r in dl], pii_check=False)

        hol = [json.loads(x) for x in (ROOT / "holidays.jsonl").read_text(
            encoding="utf-8").splitlines() if x.strip()]
        upsert_reference(s, "ngay_nghi", [
            RefRow(r["year"], {"dates": r["dates"]}, dt.date(2000, 1, 1), None, None)
            for r in hol], pii_check=False)
        s.commit()
    return len(dl), len(hol)


if __name__ == "__main__":
    nd, nh = seed()
    print(f"✓ seed thoi_hieu: {nd} loại · ngay_nghi: {nh} năm")
