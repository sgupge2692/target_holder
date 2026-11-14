"""add market_return / excess_return to predictions

目的変数を「市場平均に対する超過リターン」に変更したため、
実績として市場リターンと超過リターンを記録する。is_correct は超過リターンの符号で判定する。

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-08
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # db/init.sql（新規構築時に最初に読み込まれる）にも同じ列があるため、IF NOT EXISTS で冪等にする。
    # そうしないと、新しい DB で init.sql → alembic upgrade head の順に実行したときに
    # 「列が既に存在する」で失敗する。
    op.execute("ALTER TABLE predictions ADD COLUMN IF NOT EXISTS market_return NUMERIC")
    op.execute("ALTER TABLE predictions ADD COLUMN IF NOT EXISTS excess_return NUMERIC")


def downgrade() -> None:
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS excess_return")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS market_return")
