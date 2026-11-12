"""Materialization state and NULL-safe relation replay identity.

Existing duplicate relations cannot safely be merged automatically: their review
decisions, evidence and IDs can be referenced by bitemporal source history. Abort
with a repair instruction instead of discarding that information.

Revision ID: 0004_data_integrity
Revises: 0003_runtime_security
"""

from alembic import op

revision = "0004_data_integrity"
down_revision = "0003_runtime_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE norm_relation ADD COLUMN IF NOT EXISTS materialized_at TIMESTAMPTZ")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM norm_relation
                GROUP BY src_doc_id, src_unit_id, dst_doc_id, dst_unit_id,
                         relation_type, effective_date
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION 'norm_relation has duplicate replay identities. '
                    'Stop and reconcile duplicate IDs, evidence, review decisions '
                    'and unit_version.source_relation_id references with a reviewer '
                    'before retrying 0004_data_integrity; no rows were discarded.';
            END IF;
        END $$;
    """)
    op.execute("ALTER TABLE norm_relation DROP CONSTRAINT IF EXISTS nr_dedupe")
    op.execute("""
        ALTER TABLE norm_relation ADD CONSTRAINT nr_dedupe
        UNIQUE NULLS NOT DISTINCT
        (src_doc_id, src_unit_id, dst_doc_id, dst_unit_id, relation_type, effective_date)
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE norm_relation DROP CONSTRAINT IF EXISTS nr_dedupe")
    op.execute("""
        ALTER TABLE norm_relation ADD CONSTRAINT nr_dedupe
        UNIQUE (src_doc_id, src_unit_id, dst_doc_id, dst_unit_id, relation_type, effective_date)
    """)
    op.execute("ALTER TABLE norm_relation DROP COLUMN IF EXISTS materialized_at")
