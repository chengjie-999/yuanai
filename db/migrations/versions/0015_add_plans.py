"""新增计划闭环三表：plans / plan_steps / plan_runs（事件溯源 append-only）

Revision ID: 0015_add_plans
Revises: 0014_add_chat_envelope
Create Date: 2026-10-12

手机定计划、电脑执行：计划（draft→queued→running→done/failed）+ 步骤
（skill+意图描述，执行机现场选脚本）+ 执行记录（只 INSERT 的事件日志）。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0015_add_plans'
down_revision = '0014_add_chat_envelope'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 幂等：表已存在（create_all 兜底建过）则跳过
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = inspector.get_table_names()

    if 'plans' not in existing:
        op.create_table(
            'plans',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('user_id', sa.Integer, nullable=False, index=True),
            sa.Column('session_id', sa.String(36), nullable=False, server_default='', index=True),
            sa.Column('title', sa.String(200), nullable=False, server_default=''),
            sa.Column('goal', sa.Text, nullable=True),
            sa.Column('status', sa.String(12), nullable=False, server_default='draft'),
            sa.Column('device_id', sa.String(32), nullable=False, server_default=''),
            sa.Column('total_steps', sa.Integer, nullable=False, server_default='0'),
            sa.Column('done_steps', sa.Integer, nullable=False, server_default='0'),
            sa.Column('failed_steps', sa.Integer, nullable=False, server_default='0'),
            sa.Column('progress', sa.Integer, nullable=False, server_default='0'),
            sa.Column('message', sa.String(500), nullable=False, server_default=''),
            sa.Column('result_json', sa.Text, nullable=True),
            sa.Column('error', sa.String(1000), nullable=False, server_default=''),
            sa.Column('create_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
            sa.Column('update_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        )

    if 'plan_steps' not in existing:
        op.create_table(
            'plan_steps',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('plan_id', sa.Integer, nullable=False, index=True),
            sa.Column('user_id', sa.Integer, nullable=False, index=True),
            sa.Column('step_no', sa.Integer, nullable=False),
            sa.Column('skill', sa.String(16), nullable=False, server_default='analysis'),
            sa.Column('desc', sa.String(500), nullable=False, server_default=''),
            sa.Column('params_json', sa.Text, nullable=True),
            sa.Column('status', sa.String(12), nullable=False, server_default='pending'),
            sa.Column('attempt', sa.Integer, nullable=False, server_default='0'),
            sa.Column('progress', sa.Integer, nullable=False, server_default='0'),
            sa.Column('claimed_at', sa.TIMESTAMP, nullable=True),
            sa.Column('claimed_by', sa.String(32), nullable=False, server_default=''),
            sa.Column('started_at', sa.TIMESTAMP, nullable=True),
            sa.Column('finished_at', sa.TIMESTAMP, nullable=True),
            sa.Column('last_message', sa.String(500), nullable=False, server_default=''),
            sa.Column('result_json', sa.Text, nullable=True),
            sa.Column('error', sa.String(1000), nullable=False, server_default=''),
            sa.Column('create_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
            sa.Column('update_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('plan_id', 'step_no', name='uq_plan_step_no'),
        )

    if 'plan_runs' not in existing:
        op.create_table(
            'plan_runs',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('plan_id', sa.Integer, nullable=False, index=True),
            sa.Column('step_id', sa.Integer, nullable=True, index=True),
            sa.Column('user_id', sa.Integer, nullable=False, index=True),
            sa.Column('event', sa.String(24), nullable=False),
            sa.Column('status_from', sa.String(12), nullable=False, server_default=''),
            sa.Column('status_to', sa.String(12), nullable=False, server_default=''),
            sa.Column('message', sa.String(500), nullable=False, server_default=''),
            sa.Column('payload_json', sa.Text, nullable=True),
            sa.Column('device_id', sa.String(32), nullable=False, server_default=''),
            sa.Column('create_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table('plan_runs')
    op.drop_table('plan_steps')
    op.drop_table('plans')
