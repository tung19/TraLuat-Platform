"""Least-privilege runtime, revocable identities and append-only audit.

Revision ID: 0003_runtime_security
Revises: 0002_precedent_binding
"""
from alembic import op

revision = "0003_runtime_security"
down_revision = "0002_precedent_binding"
branch_labels = None
depends_on = None

_KB = ("authority", "document", "unit", "unit_version", "norm_relation", "chunk",
       "template", "precedent", "reference_value", "directory")


def upgrade() -> None:
    op.execute("ALTER ROLE traluat_app NOLOGIN NOSUPERUSER NOBYPASSRLS "
               "NOCREATEDB NOCREATEROLE NOREPLICATION")
    op.execute("ALTER TABLE tenant_user ADD COLUMN IF NOT EXISTS auth_subject TEXT")
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE "
               "conname='uq_tenant_user_subject' AND conrelid='tenant_user'::regclass) "
               "THEN ALTER TABLE tenant_user ADD CONSTRAINT uq_tenant_user_subject "
               "UNIQUE (tenant_id, auth_subject); END IF; END $$")
    op.execute("CREATE TABLE IF NOT EXISTS platform_operator ("
               "auth_subject TEXT PRIMARY KEY, enabled BOOLEAN NOT NULL DEFAULT true)")
    for table in _KB:
        op.execute(f"GRANT SELECT ON {table} TO traluat_app")
    for table in ("tenant", "tenant_user", "platform_operator"):
        op.execute(f"REVOKE ALL ON {table} FROM traluat_app")
        op.execute(f"GRANT SELECT ON {table} TO traluat_app")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        if table == "platform_operator":
            predicate = "auth_subject = current_setting('app.current_subject', true)"
        else:
            column = "id" if table == "tenant" else "tenant_id"
            predicate = (f"{column} = nullif("
                         "current_setting('app.current_tenant', true), '')::uuid")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} FOR SELECT USING ({predicate})")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM traluat_app")
    op.execute("GRANT SELECT, INSERT ON audit_log TO traluat_app")


def downgrade() -> None:
    # Keep audit mutation revoked even on a schema downgrade.
    for table in ("tenant", "tenant_user", "platform_operator"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP TABLE IF EXISTS platform_operator")
    op.execute("ALTER TABLE tenant_user DROP CONSTRAINT IF EXISTS uq_tenant_user_subject")
    op.execute("ALTER TABLE tenant_user DROP COLUMN IF EXISTS auth_subject")
