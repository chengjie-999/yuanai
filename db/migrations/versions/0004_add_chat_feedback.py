"""新增 ai_chat_feedback 表（AI 消息点赞）

Revision ID: 0004_add_chat_feedback
Revises: 0003_add_agent_devices
Create Date: 2026-08-27

聊天消息无 id，点赞以数组下标（message_index）定位，会话内唯一。
save_messages 全量替换时清理 message_index >= 新消息长度的孤儿行。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_add_chat_feedback'
down_revision = '0003_add_agent_devices'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 幂等：表已存在（create_all 兜底建过）则跳过
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'ai_chat_feedback' in inspector.get_table_names():
        return
    op.create_table(
        'ai_chat_feedback',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(36), nullable=False, index=True),
        sa.Column('message_index', sa.Integer, nullable=False),
        sa.Column('liked', sa.Integer, nullable=False, server_default=sa.text('0')),
        sa.Column('user_id', sa.Integer, nullable=True, index=True),
        sa.Column('create_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('session_id', 'message_index', name='uq_feedback_session_index'),
    )


def downgrade() -> None:
    op.drop_table('ai_chat_feedback')
