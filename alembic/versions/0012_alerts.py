"""alert_subscription + alert — FR-09 (bảng khách + FORCE RLS).

Revision ID: 0012_alerts
Revises: 0011_template
"""

from alembic import op

from traluat.w2.models import Base
import traluat.w5.models  # noqa: F401
from traluat.w5.rls import rls_ddl

revision = "0012_alerts"
down_revision = "0011_template"
branch_labels = None
depends_on = None

_APP = "traluat_app"


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())
    for tbl in ("alert_subscription", "alert"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO {_APP}")
        for stmt in rls_ddl(tbl):
            op.execute(stmt)
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {_APP}")


def downgrade() -> None:
    for tbl in ("alert", "alert_subscription"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {tbl}")
        op.drop_table(tbl)
