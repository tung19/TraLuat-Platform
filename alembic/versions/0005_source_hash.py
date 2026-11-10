"""document.source_hash — D6 idempotent ingest.

Revision ID: 0005_source_hash
Revises: 0004_chunk_index
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_source_hash"
down_revision = "0004_chunk_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document", sa.Column("source_hash", sa.String(), nullable=True))
    op.create_index("ix_document_source_hash", "document", ["source_hash"])


def downgrade() -> None:
    op.drop_index("ix_document_source_hash", table_name="document")
    op.drop_column("document", "source_hash")
