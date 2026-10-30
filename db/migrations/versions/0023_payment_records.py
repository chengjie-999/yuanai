"""收款记录表（2026-10-30）：单字段 paid_amount 改为逐笔记账

Revision ID: 0023_payment_records

幂等守卫（迁移纪律见 0020/0021）。既有 paid_amount 数据迁移为一条收款记录。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0023_payment_records'
down_revision = '0022_paid_amount'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    if 'payment_records' not in insp.get_table_names():
        op.create_table(
            'payment_records',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('user_id', sa.Integer, nullable=False, index=True),
            sa.Column('amount', sa.Numeric(10, 2), nullable=False),
            sa.Column('note', sa.String(200), nullable=False, server_default=''),
            sa.Column('created_at', sa.TIMESTAMP, server_default=sa.func.now()),
        )
    # 数据迁移独立于建表守卫（2026-10-30 审查修复）：表若被 create_all 兜底
    # 预建过（0020 事故同款路径），此处仍须迁移，否则删列即丢数据。
    # 按用户 NOT EXISTS 去重 = 幂等（重跑不重复插入）。
    cols = [c["name"] for c in insp.get_columns('users')]
    if 'paid_amount' in cols:
        op.execute(
            "INSERT INTO payment_records (user_id, amount) "
            "SELECT u.id, u.paid_amount FROM users u "
            "WHERE u.paid_amount > 0 AND NOT EXISTS "
            "(SELECT 1 FROM payment_records p WHERE p.user_id = u.id)")
        op.drop_column('users', 'paid_amount')


def downgrade():
    op.add_column('users', sa.Column('paid_amount', sa.Numeric(10, 2),
                                     nullable=False, server_default='0'))
    op.execute("UPDATE users u SET paid_amount = "
               "(SELECT COALESCE(SUM(amount), 0) FROM payment_records p WHERE p.user_id = u.id)")
    op.drop_table('payment_records')
