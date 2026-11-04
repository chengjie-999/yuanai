"""users.email 列（2026-11-05 R1' 邮箱验证码登录+自动注册）

邮箱 = 登录凭据（唯一，可空——存量用户名密码账号不受影响）。
VARCHAR(190)：utf8mb4 下单列索引上限内（190*4=760 字节）。
幂等守卫：加列前查列、建索引前查索引（迁移纪律见 0020/0021）。
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = '0027_user_email'
down_revision = '0026_chat_content_mediumtext'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    cols = [c["name"] for c in insp.get_columns("users")]
    if "email" not in cols:
        op.add_column("users", sa.Column("email", sa.String(190), nullable=True))
    idx_names = [i["name"] for i in insp.get_indexes("users")]
    if "ix_users_email" not in idx_names:
        op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    idx_names = [i["name"] for i in insp.get_indexes("users")]
    if "ix_users_email" in idx_names:
        op.drop_index("ix_users_email", table_name="users")
    cols = [c["name"] for c in insp.get_columns("users")]
    if "email" in cols:
        op.drop_column("users", "email")
