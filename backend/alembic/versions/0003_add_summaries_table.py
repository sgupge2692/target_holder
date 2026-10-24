"""add summaries table

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "summaries",
        sa.Column("id",           sa.Integer(),     nullable=False),
        sa.Column("code",         sa.String(10),    nullable=False),
        sa.Column("year_label",   sa.String(20),    nullable=False),   # 例: "2024秋"
        sa.Column("overview",     sa.Text(),        nullable=True),    # 会社概要
        sa.Column("performance",  sa.Text(),        nullable=True),    # 業績・見通し
        sa.Column("risks",        sa.Text(),        nullable=True),    # リスク・注意点
        sa.Column("raw_text",     sa.Text(),        nullable=True),    # 入力テキスト
        sa.Column("model",        sa.String(50),    nullable=True),    # 使用モデル名
        sa.Column("created_at",   sa.DateTime(),    nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_summaries_code",       "summaries", ["code"])
    op.create_index("ix_summaries_code_year",  "summaries", ["code", "year_label"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_summaries_code_year", table_name="summaries")
    op.drop_index("ix_summaries_code",      table_name="summaries")
    op.drop_table("summaries")
