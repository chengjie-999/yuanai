"""users 表新增 token_version 列（S3.4：JWT 吊销，+1 全量失效）

Revision ID: 0008_add_token_version
Revises: 0007_add_planet
Create Date: 2026-09-25
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0008_add_token_version'
down_revision = '0007_add_planet'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 幂等：列已存在（create_all 兜底建过）则跳过
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c["name"] for c in inspector.get_columns("users")]
    if "token_version" not in cols:
        op.add_column("users", sa.Column("token_version", sa.Integer,
                                         nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "token_version")
