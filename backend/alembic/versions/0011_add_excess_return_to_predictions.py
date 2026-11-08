"""add market_return / excess_return to predictions

目的変数を「市場平均に対する超過リターン」に変更したため、
実績として市場リターンと超過リターンを記録する。is_correct は超過リターンの符号で判定する。

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("predictions", sa.Column("market_return", sa.Numeric(), nullable=True))
    op.add_column("predictions", sa.Column("excess_return", sa.Numeric(), nullable=True))


def downgrade() -> None:
    op.drop_column("predictions", "excess_return")
    op.drop_column("predictions", "market_return")
