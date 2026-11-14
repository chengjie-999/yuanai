"""ai_chat_feedback.message_id 列（2026-11-14 #30 第二批：反馈按消息 id 定位）

下标定位在消息增删后错位——message_id 落列后按 id 定位；
message_index 保留（旧客户端兼容）。幂等守卫：加列前查列。
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = '0033_feedback_message_id'
down_revision = '0032_add_message_id'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("ai_chat_feedback")]
    if "message_id" not in cols:
        op.add_column("ai_chat_feedback", sa.Column("message_id", sa.String(36), nullable=True))
        op.create_index("ix_feedback_session_mid", "ai_chat_feedback", ["session_id", "message_id"])


def downgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("ai_chat_feedback")]
    if "message_id" in cols:
        op.drop_index("ix_feedback_session_mid", table_name="ai_chat_feedback")
        op.drop_column("ai_chat_feedback", "message_id")
