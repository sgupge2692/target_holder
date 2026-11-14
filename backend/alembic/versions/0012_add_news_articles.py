"""add news_articles

ニュース記事を毎日収集して蓄積するテーブル。
ニュース特徴量は、各日の予測時刻までに見られた記事だけで作る（過去の日付に今日の記事を混ぜない）。

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-09
"""
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # db/init.sql にも同じテーブルがあるため、IF NOT EXISTS で冪等にする（0011 と同じ理由）
    op.execute("""
        CREATE TABLE IF NOT EXISTS news_articles (
            id SERIAL PRIMARY KEY,
            code VARCHAR(10) NOT NULL,
            url_hash VARCHAR(32) NOT NULL,
            title TEXT NOT NULL,
            source VARCHAR(30),
            published_at TIMESTAMPTZ,
            first_seen_at TIMESTAMPTZ NOT NULL,
            score REAL NOT NULL DEFAULT 0,
            urgency REAL NOT NULL DEFAULT 0,
            CONSTRAINT uq_news_articles_code_url UNIQUE (code, url_hash)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_news_articles_code_seen ON news_articles (code, first_seen_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_news_articles_code_seen")
    op.execute("DROP TABLE IF EXISTS news_articles")
