"""chat_session.agent_kind 列（2026-11-13 多智能体窗口 P0：对话式 AI vs 长任务智能体）

会话级打标：chat（对话窗口，小元）/ claude / automation（执行窗口）。
打标后：sessions 接口按 kind 过滤、执行窗口消息跳过记忆折叠与自动标题、
仅 chat 可分享。存量回填：旧 @私聊会话按标题推断（「Claude Code 私聊」
→ claude、「自动化…私聊」→ automation），推断不出默认 chat。
幂等守卫：加列前查列（迁移纪律见 0020/0021 生产事故）。
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = '0031_add_session_agent_kind'
down_revision = '0030_user_prefs'
branch_labels = None
depends_on = None

_KINDS = ("chat", "claude", "automation")


def infer_legacy_kind(title: str) -> str:
    """旧 @私聊会话标题 → agent_kind（推断不出默认 chat）。纯函数，测试可注入。"""
    t = title or ""
    if "Claude Code 私聊" in t:
        return "claude"
    if "自动化" in t and "私聊" in t:
        return "automation"
    return "chat"


def backfill_legacy_kinds(bind) -> int:
    """存量回填：agent_kind='chat' 且标题命中旧私聊形态的行 → 改标。幂等。
    SQLAlchemy 2.x 连接默认不自动提交——DML 后显式 commit（alembic 迁移
    连接与测试直连两种调用形态都成立）。"""
    rows = bind.execute(sa.text(
        "SELECT session_id, title FROM chat_session WHERE agent_kind = 'chat'"
    )).fetchall()
    n = 0
    for sid, title in rows:
        kind = infer_legacy_kind(title)
        if kind == "chat":
            continue
        bind.execute(sa.text(
            "UPDATE chat_session SET agent_kind = :k WHERE session_id = :s"
        ), {"k": kind, "s": sid})
        n += 1
    if n and hasattr(bind, "commit"):
        bind.commit()
    return n


def upgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("chat_session")]
    if "agent_kind" not in cols:
        op.add_column("chat_session", sa.Column(
            "agent_kind", sa.String(20), nullable=False, server_default="chat"))
    backfill_legacy_kinds(bind)


def downgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("chat_session")]
    if "agent_kind" in cols:
        op.drop_column("chat_session", "agent_kind")
