"""payment_records.status 列（2026-11-06 盈利 MVP：充值订单闭环）

status：confirmed（已到账，计入收款）/ pending（用户已下单待人工确认）/
rejected（驳回）。存量记录默认 confirmed（原语义=已收款，逐笔记账不变）。
幂等守卫：加列前查列（迁移纪律见 0020/0021）。
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = '0029_payment_status'
down_revision = '0028_user_avatar'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("payment_records")]
    if "status" not in cols:
        op.add_column("payment_records",
                      sa.Column("status", sa.String(16), nullable=False, server_default="confirmed"))


def downgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("payment_records")]
    if "status" in cols:
        op.drop_column("payment_records", "status")
