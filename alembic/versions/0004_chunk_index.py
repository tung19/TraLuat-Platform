"""chunk — L4 derived index (pgvector + FTS). W3 §1 / data-plane §6.

Revision ID: 0004_chunk_index
Revises: 0003_debate_checkpoint
"""

from alembic import op

from traluat.w2.models import Base

revision = "0004_chunk_index"
down_revision = "0003_debate_checkpoint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # before_create DDL tạo extension vector/pg_trgm; create_all checkfirst → chỉ 'chunk'
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("chunk")
