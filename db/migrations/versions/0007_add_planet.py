"""新增知识星球四表：planets / planet_maps / planet_notes / planet_jobs

Revision ID: 0007_add_planet
Revises: 0006_add_analysis_history
Create Date: 2026-09-12

星球→导图→线性笔记三级知识库；笔记正文用 MEDIUMTEXT（中文 2 万字超 TEXT 64KB 上限）。
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT


# revision identifiers, used by Alembic.
revision = '0007_add_planet'
down_revision = '0006_add_analysis_history'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 幂等：表已存在（create_all 兜底建过）则跳过
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = inspector.get_table_names()

    if 'planets' not in existing:
        op.create_table(
            'planets',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('user_id', sa.Integer, nullable=False, index=True),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
            sa.Column('map_count', sa.Integer, nullable=False, server_default='0'),
            sa.Column('note_count', sa.Integer, nullable=False, server_default='0'),
            sa.Column('create_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
            sa.Column('update_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        )

    if 'planet_maps' not in existing:
        op.create_table(
            'planet_maps',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('planet_id', sa.Integer, nullable=False, index=True),
            sa.Column('user_id', sa.Integer, nullable=False, index=True),
            sa.Column('title', sa.String(200), nullable=False, server_default=''),
            sa.Column('source_format', sa.String(16), nullable=False, server_default='md'),
            sa.Column('origin_filename', sa.String(300), nullable=False, server_default=''),
            sa.Column('dir_path', sa.String(500), nullable=False, server_default=''),
            sa.Column('node_count', sa.Integer, nullable=False, server_default='0'),
            sa.Column('max_depth', sa.Integer, nullable=False, server_default='0'),
            sa.Column('quality', sa.String(16), nullable=False, server_default='full'),
            sa.Column('warnings', sa.Text, nullable=True),
            sa.Column('note_id', sa.Integer, nullable=True),
            sa.Column('status', sa.String(16), nullable=False, server_default='imported'),
            sa.Column('error', sa.String(500), nullable=False, server_default=''),
            sa.Column('create_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
            sa.Column('update_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        )

    if 'planet_notes' not in existing:
        op.create_table(
            'planet_notes',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('planet_id', sa.Integer, nullable=False, index=True),
            sa.Column('user_id', sa.Integer, nullable=False, index=True),
            sa.Column('map_id', sa.Integer, nullable=True, index=True),
            sa.Column('title', sa.String(200), nullable=False, server_default=''),
            sa.Column('content', MEDIUMTEXT, nullable=True),
            sa.Column('summary', sa.String(500), nullable=False, server_default=''),
            sa.Column('source', sa.String(8), nullable=False, server_default='ai'),
            sa.Column('model', sa.String(50), nullable=False, server_default=''),
            sa.Column('word_count', sa.Integer, nullable=False, server_default='0'),
            sa.Column('status', sa.String(12), nullable=False, server_default='ready'),
            sa.Column('create_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
            sa.Column('update_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        )

    if 'planet_jobs' not in existing:
        op.create_table(
            'planet_jobs',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('user_id', sa.Integer, nullable=False, index=True),
            sa.Column('planet_id', sa.Integer, nullable=True, index=True),
            sa.Column('map_id', sa.Integer, nullable=True, index=True),
            sa.Column('job_type', sa.String(16), nullable=False, server_default='import'),
            sa.Column('status', sa.String(12), nullable=False, server_default='pending'),
            sa.Column('progress', sa.Integer, nullable=False, server_default='0'),
            sa.Column('total_steps', sa.Integer, nullable=False, server_default='0'),
            sa.Column('done_steps', sa.Integer, nullable=False, server_default='0'),
            sa.Column('message', sa.String(500), nullable=False, server_default=''),
            sa.Column('result_json', sa.Text, nullable=True),
            sa.Column('error', sa.String(1000), nullable=False, server_default=''),
            sa.Column('create_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
            sa.Column('update_time', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table('planet_jobs')
    op.drop_table('planet_notes')
    op.drop_table('planet_maps')
    op.drop_table('planets')
