"""Tách DB TEST khỏi DB dev (deep-audit #3 F2/F3).

Toàn bộ test chạy trên database `traluat_test` RIÊNG — demo-seed (scripts/seed_*)
đổ vào `traluat` (dev) KHÔNG còn làm vỡ test giả-định-bảng-rỗng.

Cấp schema bằng **clone schema-only** của DB dev (pg_dump --schema-only) thay vì
replay migration: chuỗi migration hiện KHÔNG replay-được từ rỗng (0001 `create_all`
dựng `document` với cả cột `source_hash`, rồi 0005 `add_column` → trùng cột). Clone
schema-only mirror đúng schema đang chạy (extension/RLS/GiST/grant) mà không chép data.

PG của repo chạy trong container (`traluat-pg`, đổi qua env `PG_CONTAINER`). Không có
container/PG → bỏ qua lặng lẽ (mỗi test tự `pytest.skip` khi connect lỗi). KHÔNG set
`DATABASE_URL` nếu dựng hụt → tránh âm thầm chạy test lên DB dev.
"""

from __future__ import annotations

import os
import subprocess
import sys

_DEV_URL = "postgresql+psycopg://traluat:traluat@localhost:5433/traluat"
_TEST_DB = "traluat_test"
_DEV_DB = "traluat"
_CONTAINER = os.environ.get("PG_CONTAINER", "traluat-pg")


def _test_url() -> str:
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    base = os.environ.get("DATABASE_URL", _DEV_URL)
    head, _, _tail = base.rpartition("/")
    return f"{head}/{_TEST_DB}"


def _psql(db: str, sql: str) -> None:
    subprocess.run(
        ["docker", "exec", _CONTAINER, "psql", "-U", "traluat", "-d", db,
         "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=True, capture_output=True, text=True)


def _provision() -> None:
    """Drop + tạo lại `traluat_test` rồi clone schema-only từ dev (mỗi phiên → tươi)."""
    # refresh collation (image glibc mới vs volume cũ) để CREATE/DROP DATABASE chạy
    _psql(_DEV_DB, "ALTER DATABASE template1 REFRESH COLLATION VERSION")
    _psql(_DEV_DB, f'DROP DATABASE IF EXISTS "{_TEST_DB}"')
    _psql(_DEV_DB, f'CREATE DATABASE "{_TEST_DB}"')
    # clone schema-only (extension + bảng + index + RLS + grant), KHÔNG data
    clone = (f"pg_dump -U traluat --schema-only --no-owner {_DEV_DB} "
             f"| psql -U traluat -d {_TEST_DB} -v ON_ERROR_STOP=1 -q")
    subprocess.run(
        ["docker", "exec", _CONTAINER, "sh", "-c", clone],
        check=True, capture_output=True, text=True)


def pytest_configure(config):
    try:
        _provision()
    except FileNotFoundError:
        return                                  # không có docker → test tự skip
    except subprocess.CalledProcessError as e:
        print(f"\n[conftest] KHÔNG dựng được DB test ({_TEST_DB}):\n{e.stderr}",
              file=sys.stderr)
        return                                  # KHÔNG set DATABASE_URL → không chạy lên dev
    os.environ["DATABASE_URL"] = _test_url()    # mọi make_engine() → DB test
