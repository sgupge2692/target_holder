"""add paper_trades table

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_trades",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("code", sa.String(10), nullable=False, index=True),
        sa.Column("signal", sa.String(10), nullable=False),
        sa.Column("entry_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("shares", sa.Integer, nullable=False, default=100),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("exit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("exit_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(10), nullable=False, default="open"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("paper_trades")
