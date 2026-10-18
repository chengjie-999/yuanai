"""分析历史补 script_name 列 — B0 落库代码已传该参数但模型缺列（TypeError 被吞，
历史持久化实际一直失败）；补列后历史页可展示脚本名

Revision ID: 0017_add_history_script_name
Revises: 0016_add_plan_step_script
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0017_add_history_script_name'
down_revision = '0016_add_plan_step_script'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c["name"] for c in inspector.get_columns("analysis_history")]
    if "script_name" not in cols:
        op.add_column("analysis_history",
                      sa.Column("script_name", sa.String(64), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("analysis_history", "script_name")
