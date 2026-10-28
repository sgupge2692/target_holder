"""add email notification fields to users

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # メール通知設定
    op.add_column("users", sa.Column("email_signal_alert", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("email_unsubscribed", sa.Boolean(), nullable=False, server_default="false"))
    # パスワードリセット
    op.add_column("users", sa.Column("reset_token", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("reset_token_expires_at", sa.DateTime(), nullable=True))
    op.create_index("ix_users_reset_token", "users", ["reset_token"])


def downgrade() -> None:
    op.drop_index("ix_users_reset_token", "users")
    op.drop_column("users", "reset_token_expires_at")
    op.drop_column("users", "reset_token")
    op.drop_column("users", "email_unsubscribed")
    op.drop_column("users", "email_signal_alert")
