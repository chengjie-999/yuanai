"""用户自持自定义模型（2026-11-15 用户拍板：个人主体不办资质的最稳定最合规
通道——用户自己的 API key 自己与官方结算，平台零代付）

Revision ID: 0034
"""
from alembic import op
import sqlalchemy as sa

revision = "0034_user_custom_models"
down_revision = "0033_feedback_message_id"


def upgrade():
    # 幂等纪律：add_column 前查 get_columns
    conn = op.get_bind()
    inspector = __import__("sqlalchemy").inspect(conn)
    cols = [c["name"] for c in inspector.get_columns("users")]
    if "custom_models" not in cols:
        op.add_column("users", sa.Column("custom_models", sa.Text(), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = __import__("sqlalchemy").inspect(conn)
    cols = [c["name"] for c in inspector.get_columns("users")]
    if "custom_models" in cols:
        op.drop_column("users", "custom_models")
