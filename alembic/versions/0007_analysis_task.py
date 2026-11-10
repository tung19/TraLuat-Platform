"""analysis_task — async task + FORCE RLS (IDOR C6). W5 §5/§6.

Revision ID: 0007_analysis_task
Revises: 0006_tenancy_rls
"""

from alembic import op

from traluat.w2.models import Base
import traluat.w5.models  # noqa: F401
from traluat.w5.rls import rls_ddl

revision = "0007_analysis_task"
down_revision = "0006_tenancy_rls"
branch_labels = None
depends_on = None

_APP_ROLE = "traluat_app"


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())        # tạo analysis_task
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON analysis_task TO {_APP_ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {_APP_ROLE}")
    for stmt in rls_ddl("analysis_task"):               # FORCE RLS + default-deny
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON analysis_task")
    op.drop_table("analysis_task")
