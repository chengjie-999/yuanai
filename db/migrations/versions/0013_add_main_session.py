"""chat_session 新增 is_main 列（豆包式置顶主对话）

Revision ID: 0013_add_main_session
Revises: 0012_add_visit_user_id
Create Date: 2026-10-10
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0013_add_main_session'
down_revision = '0012_add_visit_user_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c["name"] for c in insp.get_columns("chat_session")]
    if "is_main" not in cols:
        op.add_column("chat_session",
                      sa.Column("is_main", sa.Integer, nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("chat_session", "is_main")
