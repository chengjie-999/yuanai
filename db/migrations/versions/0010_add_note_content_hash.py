"""planet_notes 新增 content_hash 列（Obsidian vault 同步的变更检测基础）

存量行留空 → 代码「空则现算」兼容，或跑 scripts/backfill_note_hash.py 回填。

Revision ID: 0010_add_note_content_hash
Revises: 0009_add_memory_state
Create Date: 2026-10-03
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0010_add_note_content_hash'
down_revision = '0009_add_memory_state'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c["name"] for c in insp.get_columns("planet_notes")]
    if "content_hash" not in cols:
        op.add_column("planet_notes",
                      sa.Column("content_hash", sa.String(64), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("planet_notes", "content_hash")
