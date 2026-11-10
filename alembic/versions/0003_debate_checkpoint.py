"""debate_checkpoint (resume vòng đa vai) — W4 §5.3.

Revision ID: 0003_debate_checkpoint
Revises: 0002_norm_relation
"""

from alembic import op

from traluat.w2.models import Base
import traluat.w4.checkpoint  # noqa: F401 — đăng ký DebateCheckpoint lên Base.metadata

revision = "0003_debate_checkpoint"
down_revision = "0002_norm_relation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # checkfirst=True → chỉ tạo bảng còn thiếu (debate_checkpoint)
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("debate_checkpoint")
