from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, Numeric, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.base import Base


def _now() -> datetime:
    """timezone-aware な現在時刻（utcnow() 非推奨の代替）"""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)  # 管理者フラグ

    # Stripe 関連
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan: Mapped[str] = mapped_column(String(20), default="free")  # "free" | "pro"
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # メール通知設定
    email_signal_alert: Mapped[bool] = mapped_column(Boolean, default=False)  # Proのみ
    email_unsubscribed: Mapped[bool] = mapped_column(Boolean, default=False)

    # パスワードリセット
    reset_token: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Watchlist(Base):
    """ユーザーのお気に入り銘柄"""
    __tablename__ = "watchlist"
    __table_args__ = (
        UniqueConstraint("user_id", "code", name="uq_watchlist_user_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ModelMetrics(Base):
    """MLモデルの学習・評価メトリクス履歴"""
    __tablename__ = "model_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)           # full / ensemble / tune
    mean_auc: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    std_auc: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    lgbm_auc: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    xgb_auc: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    ensemble_auc: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    n_samples: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feature_importances: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
