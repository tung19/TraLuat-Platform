"""tenant/tenant_user/audit_log + FORCE RLS + app non-owner role — W5 §2 (C2).

Revision ID: 0006_tenancy_rls
Revises: 0005_source_hash
"""

from alembic import op

from traluat.w2.models import Base
import traluat.w5.models  # noqa: F401 — đăng ký tenant/tenant_user/audit_log lên Base
from traluat.w5.rls import rls_ddl

revision = "0006_tenancy_rls"
down_revision = "0005_source_hash"
branch_labels = None
depends_on = None

_APP_ROLE = "traluat_app"


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())   # tạo tenant/tenant_user/audit_log

    # ★ C2: app role NON-OWNER, KHÔNG BYPASSRLS → policy mới có hiệu lực
    op.execute(
        f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{_APP_ROLE}') "
        f"THEN CREATE ROLE {_APP_ROLE} NOLOGIN NOBYPASSRLS; END IF; END $$;")
    op.execute(f"GRANT {_APP_ROLE} TO CURRENT_USER")           # để SET ROLE được
    for tbl in ("tenant", "tenant_user", "audit_log"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO {_APP_ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {_APP_ROLE}")

    # FORCE RLS trên bảng khách (audit_log). KB (document/unit/…) KHÔNG áp (shared).
    for stmt in rls_ddl("audit_log"):
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON audit_log")
    op.drop_table("audit_log")
    op.drop_table("tenant_user")
    op.drop_table("tenant")
