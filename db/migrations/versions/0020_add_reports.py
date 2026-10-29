"""C7 举报工单表（2026-10-29，生成式AI办法第 15 条投诉举报机制）

Revision ID: 0020_reports

幂等守卫（2026-10-30 生产事故修复）：应用启动时 create_all 兜底可能先建出
同名表（alembic 版本未戳）→ 后续 alembic upgrade 撞「Table already exists」
崩溃循环。create_table 前用 inspector 检查，表已存在则跳过直接进入 stamp。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0020_reports'
down_revision = '0019_usage_cache_hit'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if 'ai_chat_reports' in inspect(bind).get_table_names():
        return  # 已被 create_all 建过（幂等：跳过建表，仍会 stamp 本版本）
    op.create_table(
        'ai_chat_reports',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer, nullable=False, index=True),
        sa.Column('session_id', sa.String(36), nullable=False, index=True),
        sa.Column('message_index', sa.Integer, nullable=False, server_default='0'),
        sa.Column('reason', sa.String(500), nullable=False, server_default=''),
        sa.Column('content_preview', sa.Text, nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),  # pending/handled
        sa.Column('handler_note', sa.String(500), nullable=False, server_default=''),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column('handled_at', sa.TIMESTAMP, nullable=True),
    )


def downgrade():
    op.drop_table('ai_chat_reports')
