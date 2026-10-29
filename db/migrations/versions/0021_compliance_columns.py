"""C5/C6/C7 合规列（2026-10-29）：aigc 落库 / 工单 source+kind / 冻结原因+协议接受

Revision ID: 0021_compliance_columns
"""
from alembic import op
import sqlalchemy as sa

revision = '0021_compliance_columns'
down_revision = '0020_reports'
branch_labels = None
depends_on = None


def upgrade():
    # C5：AI 生成内容落库标识（《标识办法》：生成内容存储须保留标识）
    op.add_column('ai_chat', sa.Column('aigc', sa.Integer, nullable=False, server_default='0'))
    # C6：输出侧审核自动工单——source=user/auto；C7：申诉工单——kind=message/appeal
    op.add_column('ai_chat_reports', sa.Column('source', sa.String(16), nullable=False, server_default='user'))
    op.add_column('ai_chat_reports', sa.Column('kind', sa.String(16), nullable=False, server_default='message'))
    # 申诉工单无消息定位：session_id/message_index 可空
    op.alter_column('ai_chat_reports', 'session_id', existing_type=sa.String(36), nullable=True)
    op.alter_column('ai_chat_reports', 'message_index', existing_type=sa.Integer(), nullable=True)
    # C7：冻结原因（登录时展示）+ 协议接受时间（C11 登录勾选留痕）
    op.add_column('users', sa.Column('freeze_reason', sa.String(500), nullable=False, server_default=''))
    op.add_column('users', sa.Column('agreed_at', sa.TIMESTAMP, nullable=True))


def downgrade():
    op.drop_column('users', 'agreed_at')
    op.drop_column('users', 'freeze_reason')
    op.alter_column('ai_chat_reports', 'message_index', existing_type=sa.Integer(), nullable=False)
    op.alter_column('ai_chat_reports', 'session_id', existing_type=sa.String(36), nullable=False)
    op.drop_column('ai_chat_reports', 'kind')
    op.drop_column('ai_chat_reports', 'source')
    op.drop_column('ai_chat', 'aigc')
