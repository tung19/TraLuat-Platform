"""Auth — JWT → TenantContext. PAKTON lấy role từ JWT nhưng không dùng; ta dùng.

Bất biến: thiếu tenant_id trong token → MissingTenant (chặn trước engine)."""

from __future__ import annotations

import jwt

from .tenancy import TenantContext


def decode_context(token: str, secret: str, *, algorithms=("HS256",)) -> TenantContext:
    claims = jwt.decode(token, secret, algorithms=list(algorithms))
    return TenantContext(
        tenant_id=claims.get("tenant_id", ""),
        role=claims.get("role", "viewer"),
        residency_region=claims.get("residency_region", "vn"),
        retention_mode=claims.get("retention_mode", "standard"),
        tia_filed=bool(claims.get("tia_filed", False)),
    )
