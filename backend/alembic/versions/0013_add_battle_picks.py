"""add battle_picks table (予想バトル)

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "battle_picks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("prediction_id", sa.Integer, nullable=False, index=True),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("round_date", sa.String(10), nullable=False),
        sa.Column("pick", sa.String(4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "prediction_id", name="uq_battle_user_prediction"),
    )


def downgrade() -> None:
    op.drop_table("battle_picks")
