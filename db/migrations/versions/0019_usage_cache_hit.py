"""token_usage 补两列（成本指标体系 v2）：
- cache_hit_tokens：前缀缓存命中 token 数（DeepSeek 自动前缀缓存；成本分析页
  展示缓存命中率 = hit / prompt）
- purpose 已有列不变（自诞生起全记 'chat'，本次各调用点开始按用途区分）

Revision ID: 0019_usage_cache_hit
Revises: 0018_main_session_unique
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0019_usage_cache_hit'
down_revision = '0018_main_session_unique'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c["name"] for c in inspector.get_columns("token_usage")]

    if "cache_hit_tokens" not in cols:
        op.add_column("token_usage",
                      sa.Column("cache_hit_tokens", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("token_usage", "cache_hit_tokens")
