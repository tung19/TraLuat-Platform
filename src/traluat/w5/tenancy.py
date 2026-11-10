"""Multi-tenancy — ngữ cảnh tenant + RBAC. Bất biến: không request nào vào engine
mà thiếu tenant_id đã xác thực (W5 §2)."""

from __future__ import annotations

from dataclasses import dataclass

ROLES = ("owner", "lawyer", "reviewer", "viewer")


class MissingTenant(RuntimeError):
    """Request thiếu tenant_id → chặn trước khi chạm engine/LLM."""


class ResidencyViolation(RuntimeError):
    """Luồng dữ liệu khách sẽ rời VN mà tenant chưa khai TIA."""


@dataclass
class TenantContext:
    tenant_id: str
    role: str = "viewer"
    residency_region: str = "vn"
    retention_mode: str = "standard"   # standard | zero
    tia_filed: bool = False            # đã khai Transfer Impact Assessment (Luật 91/2025 Đ20)

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise MissingTenant("tenant_id rỗng")
        if self.role not in ROLES:
            raise ValueError(f"role không hợp lệ: {self.role}")


def require_role(ctx: TenantContext, *allowed: str) -> None:
    """RBAC gác (PAKTON có role trong JWT nhưng không bao giờ dùng — ta dùng)."""
    if ctx.role not in allowed:
        raise PermissionError(f"role '{ctx.role}' không đủ quyền (cần {allowed})")
