"""ai_chat 新增消息信封四列（多智能体群聊身份协议）

sender / recipient / turn / type 由编排代码填写（模型碰不到），
视图滤波（views.py）按信封裁剪每个 Agent 的上下文。

Revision ID: 0014_add_chat_envelope
Revises: 0013_add_main_session
Create Date: 2026-10-11

旧数据回填推导规则：
- role=user    → sender='user'
- role=assistant → content 的 \x00META\x00{json}\x00 前缀取 "s"，无则 'orchestrator'
- turn  = 会话内按 id 序 count(user)
- type  = 'chat'（旧工具卡在 META.t 里，不伪造 tool_result）
- recipient = ''（广播）
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0014_add_chat_envelope'
down_revision = '0013_add_main_session'
branch_labels = None
depends_on = None

_BACKFILL_BATCH = 1000


def _meta_sender(content: str):
    """从 \x00META\x00{json}\x00 前缀取 "s"；解析失败返回 None（自包含，不 import 项目代码）"""
    import json
    if not isinstance(content, str) or not content.startswith("\x00META\x00"):
        return None
    end = content.find("\x00", len("\x00META\x00"))
    if end == -1:
        return None
    try:
        meta = json.loads(content[len("\x00META\x00"):end])
    except (ValueError, TypeError):
        return None
    return str(meta.get("s") or "") if isinstance(meta, dict) else None


def _flush(conn, updates):
    if updates:
        conn.execute(sa.text(
            "UPDATE ai_chat SET sender=:sender, recipient=:recipient, "
            "turn=:turn, `type`=:type WHERE id=:id"), updates)


def _backfill(conn):
    """旧数据回填（仅本次新建列时执行一次）"""
    rows = conn.execute(sa.text(
        "SELECT id, session_id, role, content FROM ai_chat ORDER BY session_id, id")).fetchall()
    updates = []
    turn = 0
    last_sid = None
    for r in rows:
        if r.session_id != last_sid:
            turn, last_sid = 0, r.session_id
        if r.role == "user":
            turn += 1
            sender = "user"
        else:
            sender = _meta_sender(r.content) or "orchestrator"
        updates.append({"id": r.id, "sender": sender, "recipient": "",
                        "turn": turn, "type": "chat"})
        if len(updates) >= _BACKFILL_BATCH:
            _flush(conn, updates)
            updates = []
    _flush(conn, updates)


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c["name"] for c in insp.get_columns("ai_chat")]
    if "sender" in cols and "recipient" in cols and "turn" in cols and "type" in cols:
        return  # 已全部存在（幂等）
    # MySQL 保留字：type 列一律反引号
    op.add_column("ai_chat", sa.Column("sender", sa.String(32), nullable=False, server_default=""))
    op.add_column("ai_chat", sa.Column("recipient", sa.String(32), nullable=False, server_default=""))
    op.add_column("ai_chat", sa.Column("turn", sa.Integer, nullable=False, server_default="0"))
    op.add_column("ai_chat", sa.Column("type", sa.String(16), nullable=False, server_default="chat"))
    _backfill(conn)


def downgrade() -> None:
    op.drop_column("ai_chat", "type")
    op.drop_column("ai_chat", "turn")
    op.drop_column("ai_chat", "recipient")
    op.drop_column("ai_chat", "sender")
