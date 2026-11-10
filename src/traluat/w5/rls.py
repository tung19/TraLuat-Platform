"""Row-Level Security helpers (C2) — sẵn sàng áp cho bảng DỮ LIỆU KHÁCH khi có.

★ C2 — RLS mặc định FAIL-OPEN: policy bị bỏ qua im lặng nếu app role SỞ HỮU bảng
hoặc có BYPASSRLS. Chống bằng: (a) `FORCE ROW LEVEL SECURITY` (ép cả owner), (b)
app chạy role NON-OWNER không BYPASSRLS, policy mặc-định-deny. (b) là ops/role —
ghi chú; (a) + policy ở đây. KB luật (document/unit/...) là shared read-only → KHÔNG
áp RLS; chỉ bảng khách (conversations/analysis_task/audit_log/chunk client) — chưa có.
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
        f"CREATE POLICY tenant_isolation ON {table} FOR ALL "
        f"USING ({pred}) WITH CHECK ({pred})",
    ]


def set_tenant(session: Session, tenant_id: str) -> None:
    """Mở phiên theo tenant (SET LOCAL qua set_config — SQLi-safe, bind param)."""
    session.execute(
        sa.text("SELECT set_config('app.current_tenant', :t, true)"), {"t": tenant_id})
