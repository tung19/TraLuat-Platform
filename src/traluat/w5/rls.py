"""RLS bindings and runtime credential checks for customer tables.

Runtime uses a fixed non-owner role and rejects privileged login memberships.
Tenant policies default-deny without a transaction-local identity. Public legal
knowledge is shared read-only; identity and customer records enforce RLS.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session


def rls_ddl(table: str, *, tenant_col: str = "tenant_id") -> list[str]:
    """Sinh DDL bật RLS cô lập theo tenant cho 1 bảng khách.

    ★ C2: FORCE (ép cả owner) + default-deny (missing_ok=true → chưa SET var thì
    current_setting trả NULL → không khớp dòng nào) + WITH CHECK (chặn INSERT sai tenant)."""
    # NULLIF('','') → NULL: var chưa set hoặc rỗng → không khớp dòng nào (default-deny,
    # tránh lỗi cast ''::uuid).
    pred = f"{tenant_col} = nullif(current_setting('app.current_tenant', true), '')::uuid"
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"DROP POLICY IF EXISTS tenant_isolation ON {table}",
        (f"CREATE POLICY tenant_isolation ON {table} FOR ALL "
         f"USING ({pred}) WITH CHECK ({pred})"),
    ]


def set_tenant(session: Session, tenant_id: str) -> None:
    """Mở phiên theo tenant (SET LOCAL qua set_config — SQLi-safe, bind param)."""
    session.execute(
        sa.text("SELECT set_config('app.current_tenant', :t, true)"), {"t": tenant_id})


def use_app_role(session: Session) -> None:
    """Every transaction drops to the fixed non-owner, non-bypass runtime role."""
    session.execute(sa.text("SET LOCAL ROLE traluat_app"))
    unsafe = session.scalar(sa.text(
        "SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication OR EXISTS ("
        "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.relowner=pg_roles.oid AND n.nspname='public' AND c.relkind IN ('r','p')) "
        "FROM pg_roles WHERE rolname=current_user"))
    if unsafe is not False:
        raise PermissionError("runtime role must enforce row-level security")


def ensure_runtime_login(session: Session) -> None:
    """Deployment credentials themselves must not retain an owner/bypass escape."""
    unsafe = session.scalar(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_roles r WHERE "
        "(r.rolname=session_user OR pg_has_role(session_user, r.oid, 'MEMBER')) AND ("
        "r.rolsuper OR r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication OR EXISTS ("
        "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.relowner=r.oid AND n.nspname='public' AND c.relkind IN ('r','p'))))"))
    if unsafe is not False:
        raise PermissionError("runtime login must be non-owner, non-superuser and NOBYPASSRLS")


def set_identity(session: Session, tenant_id: str, subject: str) -> None:
    set_tenant(session, tenant_id)
    session.execute(sa.text("SELECT set_config('app.current_subject', :s, true)"),
                    {"s": subject})
