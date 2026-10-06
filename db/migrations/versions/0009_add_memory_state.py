"""记忆机制：ai_chat_feedback 新增 disliked 列 + 会话折叠游标表 session_memory_state

Revision ID: 0009_add_memory_state
Revises: 0008_add_token_version
Create Date: 2026-10-03
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0009_add_memory_state'
down_revision = '0008_add_token_version'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 幂等：列/表已存在（create_all 兜底建过）则跳过
    conn = op.get_bind()
    insp = sa.inspect(conn)

    cols = [c["name"] for c in insp.get_columns("ai_chat_feedback")]
    if "disliked" not in cols:
        op.add_column("ai_chat_feedback",
                      sa.Column("disliked", sa.Integer, nullable=False, server_default="0"))

    if "session_memory_state" not in insp.get_table_names():
        op.create_table(
            "session_memory_state",
            sa.Column("session_id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.Integer, nullable=True, index=True),
            sa.Column("folded_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("create_time", sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
            sa.Column("update_time", sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("session_memory_state")
    op.drop_column("ai_chat_feedback", "disliked")
