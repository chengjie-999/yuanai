"""visit_log 新增 user_id 列（登录用户行为分析：用户维度指标体系）

Revision ID: 0012_add_visit_user_id
Revises: 0011_add_token_usage
Create Date: 2026-10-09
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0012_add_visit_user_id'
down_revision = '0011_add_token_usage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c["name"] for c in insp.get_columns("visit_log")]
    if "user_id" not in cols:
        op.add_column("visit_log",
                      sa.Column("user_id", sa.Integer, nullable=True, index=True))


def downgrade() -> None:
    op.drop_column("visit_log", "user_id")
