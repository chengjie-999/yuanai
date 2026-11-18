"""0035: ai_chat (session_id, msg_id) 唯一索引——消息重复写入的数据库兜底

背景（2026-11-18 生产事故）：同一会话整段对话重复 12 遍——前端消息 id
生成不稳定（保存时才补 id），每轮保存整段重插。唯一索引让「同 id 重复行」
物理不可能（NULL msg_id 行不受限——MySQL 唯一索引允许多个 NULL）。

幂等纪律：索引已存在跳过；建索引前清理既有的同 id 重复行（保留最小 id）。
"""

from alembic import op
from sqlalchemy import inspect, text

revision = "0035_unique_session_msg_id"
down_revision = "0034_user_custom_models"

INDEX_NAME = "uq_ai_chat_session_msg"


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    idx_names = {ix["name"] for ix in insp.get_indexes("ai_chat")}
    if INDEX_NAME in idx_names:
        return
    # 先清同 id 重复行（竞态/旧数据残留），否则建索引失败
    bind.execute(text(
        "DELETE c1 FROM ai_chat c1 JOIN ai_chat c2 "
        "ON c1.session_id = c2.session_id AND c1.msg_id = c2.msg_id "
        "AND c1.msg_id IS NOT NULL AND c1.id > c2.id"
    ))
    op.create_index(INDEX_NAME, "ai_chat", ["session_id", "msg_id"], unique=True)


def downgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    idx_names = {ix["name"] for ix in insp.get_indexes("ai_chat")}
    if INDEX_NAME in idx_names:
        op.drop_index(INDEX_NAME, table_name="ai_chat")
