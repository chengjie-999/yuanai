"""添加 users.failed_login_attempts + locked_until 字段

Revision ID: 0002_add_login_security
Revises: 0001_add_theme
Create Date: 2026-07-31

登录安全加固：记录连续登录失败次数，5 次失败后临时锁定 15 分钟。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_add_login_security'
down_revision = '0001_add_theme'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'failed_login_attempts', sa.Integer, nullable=True, server_default=sa.text("0")
    ))
    op.add_column('users', sa.Column(
        'locked_until', sa.TIMESTAMP, nullable=True
    ))


def downgrade() -> None:
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
