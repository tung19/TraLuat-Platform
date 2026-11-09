"""W2 bitemporal core: authority/document/unit/unit_version + GiST EXCLUDE.

Revision ID: 0001_w2_core
Revises:
Create Date: slice-2

Tạo schema lõi từ models.Base (nguồn chân lý) + extension btree_gist (cần cho
EXCLUDE uv_no_overlap). btree_gist được bật qua event before_create của metadata.
"""

from alembic import op

from traluat.w2.models import Base

revision = "0001_w2_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)  # gồm CREATE EXTENSION btree_gist + uv_no_overlap


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
