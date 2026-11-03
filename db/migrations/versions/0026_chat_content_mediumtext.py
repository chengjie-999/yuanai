"""ai_chat.content TEXT → MEDIUMTEXT（2026-11-03 修复「消息丢失」事故）

事故：fetch_url 抓 5MB 网页全文 → 巨型 tool result 落 META → content 超过
TEXT 64KB 上限 → /chat/save 500 → 刷新后最新消息消失（DB 无记录）。
修复三层：fetch_url 返回截断 50K 字符 + tool_end 回传统一截断 20K 字符
+ 本迁移把列扩到 MEDIUMTEXT（16MB）作最终兜底。
幂等守卫：ALTER 前查列类型（迁移纪律见 0020/0021）。
"""
from alembic import op
from sqlalchemy import inspect

revision = '0026_chat_content_mediumtext'
down_revision = '0025_token_usage_multiplier'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    col = inspect(bind).get_columns('ai_chat')
    content_col = next((c for c in col if c["name"] == "content"), None)
    if content_col is None:
        return
    ctype = str(content_col["type"]).lower()
    if "text" in ctype and "medium" not in ctype and "long" not in ctype:
        op.execute("ALTER TABLE ai_chat MODIFY COLUMN content MEDIUMTEXT")


def downgrade():
    op.execute("ALTER TABLE ai_chat MODIFY COLUMN content TEXT")
