"""添加 users.theme 字段

Revision ID: 0001_add_theme
Revises: None
Create Date: 2026-07-28

用户表新增 theme 字段，用于存储用户主题偏好设置。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_add_theme'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 幂等：检查列是否已存在（兼容 create_all 先建表的情况）
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('users')]
    if 'theme' not in columns:
        op.add_column('users', sa.Column(
            'theme', sa.String(10), nullable=True, server_default=sa.text("''")
        ))


def downgrade() -> None:
    op.drop_column('users', 'theme')
