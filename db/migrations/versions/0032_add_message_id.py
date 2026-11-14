"""ai_chat.msg_id 列（2026-11-14 #30 消息 id 架构债第一步：保存幂等化）

消息按 id 定位（点赞/修改/重发/删除/多端同步 diff/SSE 重连去重），
替代「数组下标 + 全量替换」模式——旧快照晚到覆盖新消息、委派剥离
下标错位等竞态的根治。msg_id 可空：旧数据 NULL，旧客户端（不带 id
的保存）继续走全量替换兼容路径。
幂等守卫：加列前查列（迁移纪律见 0020/0021 生产事故）。
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = '0032_add_message_id'
down_revision = '0031_add_session_agent_kind'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("ai_chat")]
    if "msg_id" not in cols:
        op.add_column("ai_chat", sa.Column("msg_id", sa.String(36), nullable=True))
        # 会话内按 id 幂等 upsert 的定位索引（NULL 不冲突，旧数据不受影响）
        op.create_index("ix_ai_chat_session_msg", "ai_chat", ["session_id", "msg_id"])


def downgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("ai_chat")]
    if "msg_id" in cols:
        op.drop_index("ix_ai_chat_session_msg", table_name="ai_chat")
        op.drop_column("ai_chat", "msg_id")
