"""Tách DB TEST khỏi DB dev (deep-audit #3 F2/F3/F7).

Toàn bộ test chạy trên database `traluat_test` RIÊNG — demo-seed (scripts/seed_*)
đổ vào `traluat` (dev) KHÔNG còn làm vỡ test giả-định-bảng-rỗng.

Dựng schema bằng **alembic upgrade head** (chuỗi migration đã squash về baseline
replay-được-từ-rỗng, F8) — không còn phụ thuộc docker/pg_dump. Mỗi phiên drop+tạo lại
`traluat_test` rồi migrate → luôn khớp migration mới nhất.

Không có Postgres → bỏ qua lặng lẽ (mỗi test tự `pytest.skip` khi connect lỗi). Lỗi
dựng KHÁC (migrate hỏng) → cảnh báo rõ + KHÔNG set DATABASE_URL (tránh âm thầm chạy
test lên DB dev). Ghi đè URL qua env `TEST_DATABASE_URL`.
"""

from __future__ import annotations

import os
import sys

import sqlalchemy as sa

_DEV_URL = "postgresql+psycopg://traluat:traluat@localhost:5433/traluat"
_TEST_DB = "traluat_test"


def _test_url() -> str:
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    base = os.environ.get("DATABASE_URL", _DEV_URL)
    head, _, _tail = base.rpartition("/")
    return f"{head}/{_TEST_DB}"


def _recreate_database(admin_url: str, name: str) -> None:
    eng = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
    try:
        with eng.connect() as c:
            # image gộp (glibc mới) + volume cũ → template1 lệch collation → CREATE fail
            try:
                c.execute(sa.text("ALTER DATABASE template1 REFRESH COLLATION VERSION"))
            except Exception:  # noqa: BLE001,S110 — best-effort; không được → CREATE tự báo
                pass
            c.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}"'))   # mỗi phiên → tươi
            c.execute(sa.text(f'CREATE DATABASE "{name}"'))
    finally:
        eng.dispose()


def _migrate(url: str) -> None:
    from alembic.config import Config

    from alembic import command
    os.environ["DATABASE_URL"] = url            # env.py đọc database_url() → URL test
    command.upgrade(Config("alembic.ini"), "head")


def pytest_configure(config):
    admin = os.environ.get("DATABASE_URL", _DEV_URL)       # DB có sẵn để DROP/CREATE
    test_url = _test_url()
    try:
        _recreate_database(admin, _TEST_DB)
        _migrate(test_url)
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        if "could not" not in msg and "connection" not in msg and "does not exist" not in msg:
            print(f"\n[conftest] KHÔNG dựng được DB test ({_TEST_DB}): {e}", file=sys.stderr)
        return                                  # không PG / lỗi → test tự skip
    os.environ["DATABASE_URL"] = test_url                   # mọi make_engine() → DB test
