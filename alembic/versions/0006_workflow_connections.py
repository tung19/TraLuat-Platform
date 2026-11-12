"""Reviewed amendment identity and idempotent tenant alert materialization."""
from alembic import op

revision = "0006_workflow_connections"
down_revision = "0005_embedding_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE norm_relation ADD COLUMN IF NOT EXISTS applied_payload_hash TEXT")
    op.execute("ALTER TABLE alert_subscription ADD COLUMN IF NOT EXISTS created_at "
               "TIMESTAMPTZ NOT NULL DEFAULT now()")
    op.execute("ALTER TABLE alert ADD COLUMN IF NOT EXISTS source_relation_id "
               "INTEGER REFERENCES norm_relation(id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_alert_tenant_relation "
               "ON alert (tenant_id, source_relation_id)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_alert_tenant_relation")
    op.execute("ALTER TABLE alert DROP COLUMN IF EXISTS source_relation_id")
    op.execute("ALTER TABLE alert_subscription DROP COLUMN IF EXISTS created_at")
    op.execute("ALTER TABLE norm_relation DROP COLUMN IF EXISTS applied_payload_hash")
