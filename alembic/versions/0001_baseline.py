"""Baseline schema — squash 0001…0013 thành MỘT migration replay-được-từ-rỗng.

Lý do (deep-audit #3 F8): chuỗi cũ trộn `create_all` (phản ánh model HIỆN TẠI) với
`add_column` sau đó → replay từ DB rỗng bị trùng cột ('source_hash already exists') →
fresh-deploy/CI fail. Baseline này dựng toàn schema một lần, đúng thứ tự phụ thuộc:

  1. CREATE EXTENSION postgis (vector/btree_gist/pg_trgm do event before_create của
     models tự tạo khi create_all).
  2. create_all TẤT CẢ bảng (import đủ model → metadata đầy đủ): KB (authority/document/
     unit/unit_version/norm_relation/chunk/template/precedent/reference_value/
     debate_checkpoint) + khách (tenant/tenant_user/audit_log/analysis_task/alert/
     alert_subscription) + directory. Gồm GiST uv_no_overlap, GIN tsv, HNSW embedding.
  3. Role app NON-OWNER + grants + FORCE RLS bảng khách tenant-scoped.

DB đang chạy (đã ở 0013) → `alembic stamp 0001_baseline` (không chạy lại, giữ data).

⚠️ Convention: baseline `create_all` phản ánh MODEL HIỆN TẠI → DB rỗng luôn có schema
mới nhất. Vì vậy MỌI migration delta sau baseline PHẢI idempotent (`ADD COLUMN IF NOT
EXISTS`…) để no-op trên DB mới, chỉ thực-áp trên DB đã deploy ở baseline cũ. (Hoặc:
định kỳ "freeze" baseline mới.)

Revision ID: 0001_baseline
Revises:
"""

import traluat.tools.directory
import traluat.w4.checkpoint
import traluat.w5.models  # noqa: F401 — tenant/audit/alert/analysis_task lên Base
from alembic import op
from traluat.w2.models import Base
from traluat.w5.rls import rls_ddl

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

_APP = "traluat_app"
_RLS_TABLES = ("audit_log", "analysis_task", "alert", "alert_subscription")  # FORCE RLS
_WRITE_TABLES = ("tenant", "tenant_user", *_RLS_TABLES)                      # app ghi được


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")   # geometry (directory) — trước create_all
    Base.metadata.create_all(bind=op.get_bind())           # mọi bảng + index + GiST/GIN/HNSW

    # App role NON-OWNER (C2: NOBYPASSRLS → policy có hiệu lực). Idempotent.
    op.execute(
        f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{_APP}') "
        f"THEN CREATE ROLE {_APP} NOLOGIN NOBYPASSRLS; END IF; END $$;")
    op.execute(f"GRANT {_APP} TO CURRENT_USER")            # để SET ROLE được
    for tbl in _WRITE_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO {_APP}")
    op.execute(f"GRANT SELECT ON directory TO {_APP}")     # danh bạ công: chỉ đọc
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {_APP}")

    for tbl in _RLS_TABLES:                                # FORCE RLS + default-deny
        for stmt in rls_ddl(tbl):
            op.execute(stmt)


def downgrade() -> None:
    for tbl in _RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {tbl}")
    Base.metadata.drop_all(bind=op.get_bind())
