"""template — FR-34 TES (mẫu đơn).

Revision ID: 0011_template
Revises: 0010_task_payload
"""

from alembic import op

from traluat.w2.models import Base

revision = "0011_template"
down_revision = "0010_task_payload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("template")
