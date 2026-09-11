"""新增 analysis_history 表（分析大屏结果持久化）

Revision ID: 0006_add_analysis_history
Revises: 0005_add_visit_log
Create Date: 2026-09-11

分析脚本 __DASHBOARD__ 结果落库；Redis dashboard:{session_id}（TTL 1h）
过期后 GET /analysis/dashboard 从此表恢复最新结果。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006_add_analysis_history'
down_revision = '0005_add_visit_log'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 幂等：表已存在（create_all 兜底建过）则跳过
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'analysis_history' in inspector.get_table_names():
        return
    op.create_table(
        'analysis_history',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(36), nullable=False, index=True),
        sa.Column('dataset_id', sa.Integer, nullable=True),
        sa.Column('result_json', sa.Text, nullable=False),
        sa.Column('create_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('analysis_history')
