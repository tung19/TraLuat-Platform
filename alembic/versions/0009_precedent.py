"""precedent — án lệ/bản án tham chiếu (W4 §2).

Revision ID: 0009_precedent
Revises: 0008_reference_value
"""

from alembic import op

from traluat.w2.models import Base

revision = "0009_precedent"
down_revision = "0008_reference_value"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("precedent")
