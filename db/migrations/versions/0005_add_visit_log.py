"""新增 visit_log 表（网站访问埋点）

Revision ID: 0005_add_visit_log
Revises: 0004_add_chat_feedback
Create Date: 2026-09-11

前端 LandingPage/AboutPage 挂载时上报 POST /stats/visit，后台仪表盘统计 PV/UV。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005_add_visit_log'
down_revision = '0004_add_chat_feedback'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 幂等：表已存在（create_all 兜底建过）则跳过
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'visit_log' in inspector.get_table_names():
        return
    op.create_table(
        'visit_log',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('path', sa.String(200), nullable=False, server_default=sa.text("'/'")),
        sa.Column('ip', sa.String(64), nullable=True),
        sa.Column('user_agent', sa.String(300), nullable=True),
        sa.Column('create_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('visit_log')
