"""add model_metrics table

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "model_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trained_at", sa.DateTime(), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("mean_auc", sa.Numeric(6, 4), nullable=True),
        sa.Column("std_auc", sa.Numeric(6, 4), nullable=True),
        sa.Column("lgbm_auc", sa.Numeric(6, 4), nullable=True),
        sa.Column("xgb_auc", sa.Numeric(6, 4), nullable=True),
        sa.Column("ensemble_auc", sa.Numeric(6, 4), nullable=True),
        sa.Column("n_samples", sa.Integer(), nullable=True),
        sa.Column("feature_importances", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_metrics_trained_at", "model_metrics", ["trained_at"])


def downgrade():
    op.drop_index("ix_model_metrics_trained_at", table_name="model_metrics")
    op.drop_table("model_metrics")
