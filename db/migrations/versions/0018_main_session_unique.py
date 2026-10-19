"""主对话唯一性——ensure_main_session 的 check-then-insert 竞态可能产生同一用户多个
is_main=1（并发登录/多标签页）。MySQL 不支持部分索引，用计算列 main_uid
（is_main=1 时=user_id，否则 NULL）+ 唯一索引兜底；存量重复先去重
（保留 update_time 最新的一条，同秒并列取最小 id）。

Revision ID: 0018_main_session_unique
Revises: 0017_add_history_script_name
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0018_main_session_unique'
down_revision = '0017_add_history_script_name'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c["name"] for c in inspector.get_columns("chat_session")]

    if "main_uid" not in cols:
        # 1) 计算列（is_main=1 时 = user_id，否则 NULL；CASE WHEN 兼容 MySQL/SQLite）
        op.add_column("chat_session",
                      sa.Column("main_uid", sa.BigInteger(),
                                sa.Computed("CASE WHEN is_main = 1 THEN user_id END", persisted=True)))
        # 2) 存量重复去重：每用户保留 update_time 最新（同秒取最小 id）的主对话，其余降级普通会话
        op.execute("""
            UPDATE chat_session c
            LEFT JOIN (
                SELECT t.user_id, MIN(t.id) AS keep_id
                FROM chat_session t
                JOIN (
                    SELECT user_id, MAX(update_time) AS mt
                    FROM chat_session WHERE is_main = 1 GROUP BY user_id
                ) m ON m.user_id = t.user_id AND t.update_time = m.mt
                WHERE t.is_main = 1
                GROUP BY t.user_id
            ) k ON k.user_id = c.user_id AND k.keep_id = c.id
            SET c.is_main = 0
            WHERE c.is_main = 1 AND k.keep_id IS NULL
        """)
        # 3) 唯一索引（NULL 不冲突 → 效果 = 每用户至多一条主对话）
        op.create_index("uq_chat_session_main_uid", "chat_session", ["main_uid"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_chat_session_main_uid", table_name="chat_session")
    op.drop_column("chat_session", "main_uid")
