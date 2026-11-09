"""norm_relation (amends/repeals… + dedupe) — slice-3.

Revision ID: 0002_norm_relation
Revises: 0001_w2_core
"""

from alembic import op

from traluat.w2.models import Base

revision = "0002_norm_relation"
down_revision = "0001_w2_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # checkfirst=True (mặc định) → chỉ tạo bảng còn thiếu (norm_relation)
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("norm_relation")
