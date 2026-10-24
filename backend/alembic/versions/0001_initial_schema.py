"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TimescaleDB拡張（init.sqlで作成済みの場合はスキップ）
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "listed_stocks",
        sa.Column("code",         sa.String(10),  primary_key=True),
        sa.Column("company_name", sa.String(255)),
        sa.Column("market_code",  sa.String(10)),
        sa.Column("sector_code",  sa.String(10)),
        sa.Column("updated_at",   sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "daily_quotes",
        sa.Column("code",           sa.String(10), nullable=False),
        sa.Column("date",           sa.Date,       nullable=False),
        sa.Column("open",           sa.Numeric),
        sa.Column("high",           sa.Numeric),
        sa.Column("low",            sa.Numeric),
        sa.Column("close",          sa.Numeric),
        sa.Column("volume",         sa.BigInteger),
        sa.Column("turnover_value", sa.Numeric),
        sa.Column("adj_open",       sa.Numeric),
        sa.Column("adj_high",       sa.Numeric),
        sa.Column("adj_low",        sa.Numeric),
        sa.Column("adj_close",      sa.Numeric),
        sa.Column("adj_volume",     sa.BigInteger),
        sa.Column("adj_factor",     sa.Numeric),
        sa.PrimaryKeyConstraint("code", "date"),
    )
    op.execute("SELECT create_hypertable('daily_quotes', 'date', if_not_exists => TRUE)")

    # features テーブル（ret_lag_1..20 を動的に生成）
    ret_lag_cols = [sa.Column(f"ret_lag_{i}", sa.Numeric) for i in range(1, 21)]
    op.create_table(
        "features",
        sa.Column("code",            sa.String(10), nullable=False),
        sa.Column("date",            sa.Date,       nullable=False),
        sa.Column("ma5_deviation",   sa.Numeric),
        sa.Column("ma25_deviation",  sa.Numeric),
        sa.Column("ma75_deviation",  sa.Numeric),
        sa.Column("golden_cross",    sa.SmallInteger),
        sa.Column("dead_cross",      sa.SmallInteger),
        sa.Column("bb_percent_b",    sa.Numeric),
        sa.Column("bb_width",        sa.Numeric),
        sa.Column("rsi",             sa.Numeric),
        sa.Column("macd_diff",       sa.Numeric),
        sa.Column("volume_ratio",    sa.Numeric),
        sa.Column("price_up_vol_up", sa.SmallInteger),
        sa.Column("body_ratio",      sa.Numeric),
        sa.Column("upper_shadow",    sa.Numeric),
        sa.Column("lower_shadow",    sa.Numeric),
        *ret_lag_cols,
        sa.Column("next_return",     sa.Numeric),
        sa.Column("label",           sa.SmallInteger),
        sa.PrimaryKeyConstraint("code", "date"),
    )

    op.create_table(
        "predictions",
        sa.Column("id",             sa.Integer,    primary_key=True, autoincrement=True),
        sa.Column("code",           sa.String(10), nullable=False),
        sa.Column("date",           sa.Date,       nullable=False),
        sa.Column("up_probability", sa.Numeric,    nullable=False),
        sa.Column("signal",         sa.String(10), nullable=False),
        sa.Column("predicted_at",   sa.DateTime,   server_default=sa.func.now()),
        sa.Column("actual_return",  sa.Numeric),
        sa.Column("is_correct",     sa.Boolean),
        sa.UniqueConstraint("code", "date", name="uq_predictions_code_date"),
    )

    # インデックス
    op.create_index("idx_daily_quotes_code", "daily_quotes", ["code"])
    op.create_index("idx_daily_quotes_date", "daily_quotes", [sa.text("date DESC")])
    op.create_index("idx_features_code",     "features",     ["code"])
    op.create_index("idx_features_date",     "features",     [sa.text("date DESC")])
    op.create_index("idx_predictions_code",  "predictions",  ["code"])
    op.create_index("idx_predictions_date",  "predictions",  [sa.text("date DESC")])


def downgrade() -> None:
    op.drop_table("predictions")
    op.drop_table("features")
    op.drop_table("daily_quotes")
    op.drop_table("listed_stocks")
