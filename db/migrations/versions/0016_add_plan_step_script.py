"""计划步骤加 script 列 — 融合后本地统筹建计划时绑定脚本名，执行器零 LLM 直跑

Revision ID: 0016_add_plan_step_script
Revises: 0015_add_plans
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0016_add_plan_step_script'
down_revision = '0015_add_plans'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c["name"] for c in inspector.get_columns("plan_steps")]
    if "script" not in cols:
        op.add_column("plan_steps",
                      sa.Column("script", sa.String(64), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("plan_steps", "script")
