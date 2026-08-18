"""新增 agent_devices 表（Agent 机器识别）

Revision ID: 0003_add_agent_devices
Revises: 0002_add_login_security
Create Date: 2026-08-16

本地 Agent 设备表：后台签发安装码（agent_secret 为空 = 未注册），
本机 --install 注册时消费安装码并填充 agent_secret；user_id 一对一绑定云端用户。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_add_agent_devices'
down_revision = '0002_add_login_security'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 幂等：表已存在（create_all 兜底建过）则跳过
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'agent_devices' in inspector.get_table_names():
        return
    op.create_table(
        'agent_devices',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('install_code', sa.String(32), unique=True, nullable=False),
        sa.Column('agent_secret', sa.String(64), nullable=False, server_default=sa.text("''")),
        sa.Column('machine_name', sa.String(64), nullable=False, server_default=sa.text("''")),
        sa.Column('user_id', sa.Integer, nullable=True, index=True),
        sa.Column('enabled', sa.Integer, nullable=False, server_default=sa.text('1')),
        sa.Column('last_seen', sa.TIMESTAMP, nullable=True),
        sa.Column('create_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('agent_devices')
