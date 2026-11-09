"""users.prefs JSON 列（2026-11-09 多端同步 P1：偏好上云）

存用户跨端偏好（娱乐模式/云端本机三态/自动朗读/小窗定向/@粘性定向），
JSON 文本列；空串 = 未设置（前端 localStorage 兜底）。白名单校验在
/api/v1/auth/prefs 端点做，本列只做存储。
幂等守卫：加列前查列（迁移纪律见 0020/0021）。
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = '0030_user_prefs'
down_revision = '0029_payment_status'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("users")]
    if "prefs" not in cols:
        # 注意：MySQL TEXT 不能带 server_default（1101）——无 server_default，
        # 存量行自动填 ''；写入侧读-改-写兜底空串
        op.add_column("users", sa.Column("prefs", sa.Text, nullable=False))


def downgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("users")]
    if "prefs" in cols:
        op.drop_column("users", "prefs")
