"""precedent.effective_from — CN-04 án lệ ràng buộc (NQ 04/2019).

Revision ID: 0002_precedent_binding
Revises: 0001_baseline

⚠️ Convention (vì baseline dùng `create_all` phản ánh MODEL HIỆN TẠI → DB rỗng đã có
cột này): migration delta phải IDEMPOTENT (`IF NOT EXISTS`) để no-op trên DB mới,
chỉ thực-áp trên DB đã deploy ở baseline cũ.
"""

from alembic import op

revision = "0002_precedent_binding"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE precedent ADD COLUMN IF NOT EXISTS effective_from DATE")


def downgrade() -> None:
    op.execute("ALTER TABLE precedent DROP COLUMN IF EXISTS effective_from")
