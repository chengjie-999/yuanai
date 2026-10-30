"""会话回收站（2026-10-30）：ChatSession.deleted_at 软删除列

Revision ID: 0024_session_deleted_at

幂等守卫（迁移纪律见 0020/0021）。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0024_session_deleted_at'
down_revision = '0023_payment_records'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns('chat_session')]
    if 'deleted_at' not in cols:
        op.add_column('chat_session', sa.Column('deleted_at', sa.TIMESTAMP, nullable=True))


def downgrade():
    op.drop_column('chat_session', 'deleted_at')
