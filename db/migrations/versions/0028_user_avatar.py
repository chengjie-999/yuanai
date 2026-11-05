"""users.avatar 列（2026-11-06 用户头像上传）

存公开路径（如 /api/v1/user-avatar/3?v=1762345678），空 = 前端默认首字圆。
幂等守卫：加列前查列（迁移纪律见 0020/0021）。
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = '0028_user_avatar'
down_revision = '0027_user_email'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("users")]
    if "avatar" not in cols:
        op.add_column("users", sa.Column("avatar", sa.String(255), nullable=False, server_default=""))


def downgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("users")]
    if "avatar" in cols:
        op.drop_column("users", "avatar")
