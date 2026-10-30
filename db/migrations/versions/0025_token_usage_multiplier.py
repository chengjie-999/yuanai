"""盈利系数快照（2026-10-30 用户拍板）：token_usage.multiplier 列

Revision ID: 0025_token_usage_multiplier

历史消费锁定：新写入的用量记录按写入时刻的盈利系数快照；存量行回填发布时
默认系数 1.8（此后改系数只影响新消费）。幂等守卫（迁移纪律见 0020/0021）。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0025_token_usage_multiplier'
down_revision = '0024_session_deleted_at'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns('token_usage')]
    if 'multiplier' not in cols:
        op.add_column('token_usage', sa.Column('multiplier', sa.Numeric(5, 2), nullable=True))
        # 存量回填发布时默认系数 1.8（历史消费按 1.8 锁定；NULL 在聚合时兜底取当前系数）
        op.execute("UPDATE token_usage SET multiplier = 1.8 WHERE multiplier IS NULL")


def downgrade():
    op.drop_column('token_usage', 'multiplier')
