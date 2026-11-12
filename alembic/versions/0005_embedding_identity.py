"""Record embedding identity; legacy vectors require reindexing for dense search."""
from alembic import op

revision = "0005_embedding_identity"
down_revision = "0004_data_integrity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE chunk ADD COLUMN IF NOT EXISTS embedding_model TEXT")


def downgrade():
    op.execute("ALTER TABLE chunk DROP COLUMN IF EXISTS embedding_model")
