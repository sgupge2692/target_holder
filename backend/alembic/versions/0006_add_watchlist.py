"""add watchlist table

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist",
        sa.Column("id",           sa.Integer(),    primary_key=True),
        sa.Column("user_id",      sa.Integer(),    sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code",         sa.String(20),   nullable=False),
        sa.Column("company_name", sa.String(255),  nullable=True),
        sa.Column("created_at",   sa.DateTime(),   server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_watchlist_user_id", "watchlist", ["user_id"])
    op.create_index("ix_watchlist_code",    "watchlist", ["code"])
    op.create_unique_constraint(
        "uq_watchlist_user_code", "watchlist", ["user_id", "code"]
    )


def downgrade() -> None:
    op.drop_table("watchlist")
