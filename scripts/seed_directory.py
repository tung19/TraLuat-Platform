"""Seed danh bạ geo (FR-39) từ data/seed/directory.jsonl → bảng `directory`.

Idempotent: bỏ qua mục đã có (trùng name+province). Chạy:
    uv run python scripts/seed_directory.py [path.jsonl]
Cần image Postgres có PostGIS (deploy/postgres) + migration 0013 đã chạy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w1.directory import Directory, DirectoryQuarantined, add_directory_entry
from traluat.w2.db import make_engine

DEFAULT = Path(__file__).resolve().parent.parent / "data" / "seed" / "directory.jsonl"


def seed(path: Path) -> tuple[int, int, int]:
    loaded = skipped = quarantined = 0
    with Session(make_engine(), future=True) as s:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            exists = s.scalar(sa.select(Directory.id).where(
                Directory.name == r["name"], Directory.province == r.get("province")))
            if exists:
                skipped += 1
                continue
            try:
                add_directory_entry(
                    s, r["kind"], r["name"], address=r.get("address"),
                    province=r.get("province"), phone=r.get("phone"),
                    email=r.get("email"), lat=r.get("lat"), lon=r.get("lon"),
                    extra=r.get("extra"))
                loaded += 1
            except DirectoryQuarantined as e:
                print(f"  ⚠ quarantine: {e}")
                quarantined += 1
        s.commit()
    return loaded, skipped, quarantined


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    loaded, skipped, quarantined = seed(p)
    print(f"✓ seed {p.name}: +{loaded} mới · {skipped} đã có · {quarantined} quarantine")
