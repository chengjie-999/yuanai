"""token 用量统计表（支付与金融分析的账本地基）

Revision ID: 0011_add_token_usage
Revises: 0010_add_note_content_hash
Create Date: 2026-10-03
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0011_add_token_usage'
down_revision = '0010_add_note_content_hash'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "token_usage" not in insp.get_table_names():
        op.create_table(
            "token_usage",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer, nullable=True, index=True),
            sa.Column("model", sa.String(64), nullable=False, server_default=""),
            sa.Column("purpose", sa.String(32), nullable=False, server_default="chat"),
            sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
            sa.Column("source", sa.String(16), nullable=False, server_default="cloud"),
            sa.Column("create_time", sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("token_usage")
