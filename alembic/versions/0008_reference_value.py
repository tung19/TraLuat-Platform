"""reference_value — reference-data plane (luồng 3). data-plane §2.

Revision ID: 0008_reference_value
Revises: 0007_analysis_task
"""

from alembic import op

from traluat.w2.models import Base

revision = "0008_reference_value"
down_revision = "0007_analysis_task"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("reference_value")
