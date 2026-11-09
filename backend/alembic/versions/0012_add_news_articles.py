"""add news_articles

ニュース記事を毎日収集して蓄積するテーブル。
ニュース特徴量は、各日の予測時刻までに見られた記事だけで作る（過去の日付に今日の記事を混ぜない）。

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("url_hash", sa.String(32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source", sa.String(30), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.REAL(), nullable=False, server_default="0"),
        sa.Column("urgency", sa.REAL(), nullable=False, server_default="0"),
        sa.UniqueConstraint("code", "url_hash", name="uq_news_articles_code_url"),
    )
    op.create_index("idx_news_articles_code_seen", "news_articles", ["code", "first_seen_at"])


def downgrade() -> None:
    op.drop_index("idx_news_articles_code_seen", table_name="news_articles")
    op.drop_table("news_articles")
