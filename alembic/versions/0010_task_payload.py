"""analysis_task.payload — Celery worker tái dựng job.

Revision ID: 0010_task_payload
Revises: 0009_precedent
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010_task_payload"
down_revision = "0009_precedent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_task", sa.Column("payload", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_task", "payload")
