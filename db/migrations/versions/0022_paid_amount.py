"""收款金额列（2026-10-30）：线下收款由管理员手动填写

Revision ID: 0022_paid_amount

幂等守卫（迁移纪律见 0020/0021）：add_column 前 inspector 检查。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0022_paid_amount'
down_revision = '0021_compliance_columns'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns('users')]
    if 'paid_amount' not in cols:
        op.add_column('users', sa.Column('paid_amount', sa.Numeric(10, 2),
                                         nullable=False, server_default='0'))


def downgrade():
    op.drop_column('users', 'paid_amount')
