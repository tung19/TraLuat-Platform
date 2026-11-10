"""directory — FR-39/40 danh bạ geo (PostGIS point + GiST).

Revision ID: 0013_directory
Revises: 0012_alerts
"""

import traluat.w1.directory  # noqa: F401  (đăng ký model + geoalchemy2 DDL)
from alembic import op
from traluat.w2.models import Base

revision = "0013_directory"
down_revision = "0012_alerts"
branch_labels = None
depends_on = None

_APP = "traluat_app"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")   # FR-39 geo
    Base.metadata.create_all(bind=op.get_bind())           # directory + spatial GiST
    # Danh bạ là KB CÔNG (không RLS) — app role đọc; ghi qua pipeline ingest (owner).
    op.execute(f"GRANT SELECT ON directory TO {_APP}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {_APP}")


def downgrade() -> None:
    op.drop_table("directory")
