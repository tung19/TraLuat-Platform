# Bằng chứng sau sửa — 10/11/2026

- `core-tests.log`: venv sạch, PostgreSQL test riêng, **360 passed / 8 skipped**.
- `model-tests.log`: BGE/NLI thật từ cache offline, **7 passed**.
- `no-db-tests.log`: không TEST_DATABASE_URL, kiểm harness không dùng DB dev.
- Ruff `src tests scripts`: pass; `uv lock --check --offline`: pass; `git diff --check`: pass.
- Compile Python source/tests/scripts/migrations: 166 file pass.

Core chạy trên Python 3.12, package cài từ `uv sync --locked --extra geo`, PostgreSQL 16 có vector + PostGIS. Migration từ trắng tới `0004_data_integrity`. Core skip optional models/OCR/Neo4j/OpenTelemetry; BGE/NLI chạy riêng bằng venv có model cache. Test dữ liệu dùng fixture giả và transaction rollback; một số test provider commit fixture để kiểm durability rồi cleanup.

Container riêng `traluat-fix-20261110` sử dụng localhost 55433 và tmpfs, được xóa sau kiểm chứng. Không migrate/ghi vào DB dev 5433 hoặc Neo4j hiện có. Chưa commit/push/deploy.

Phạm vi sửa, hướng dẫn nâng cấp và giới hạn: [audit-fixes-2026-11-10.md](../../docs/audit-fixes-2026-11-10.md).
