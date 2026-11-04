from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, Numeric, Text, ForeignKey, UniqueConstraint, Date
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


# ────────────────────────────────────────────────────────────
# 資産管理
# ────────────────────────────────────────────────────────────

ASSET_CATEGORIES = [
    "cash",        # 現金・預金
    "stock",       # 株式・投資信託
    "realestate",  # 不動産
    "vehicle",     # 車・乗り物
    "other",       # その他資産
    "liability",   # 負債・ローン
]


class PaperTrade(Base):
    """ペーパートレード記録（仮想売買）"""
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    signal: Mapped[str] = mapped_column(String(10), nullable=False)         # UP / DOWN
    entry_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    entry_date: Mapped[Date] = mapped_column(Date, nullable=False)          # type: ignore[valid-type]
    exit_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    exit_date: Mapped[Date | None] = mapped_column(Date, nullable=True)     # type: ignore[valid-type]
    status: Mapped[str] = mapped_column(String(10), default="open")         # open / closed
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class AssetAccount(Base):
    """資産口座・項目マスタ（ユーザーが自由に追加）"""
    __tablename__ = "asset_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)          # "三菱UFJ普通預金", "自宅" など
    category: Mapped[str] = mapped_column(String(20), nullable=False)       # ASSET_CATEGORIES のいずれか
    currency: Mapped[str] = mapped_column(String(10), default="JPY")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class AssetSnapshot(Base):
    """資産残高スナップショット（日次）"""
    __tablename__ = "asset_snapshots"
    __table_args__ = (
        UniqueConstraint("account_id", "snapshot_date", name="uq_asset_snapshot_account_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("asset_accounts.id", ondelete="CASCADE"), index=True)
    snapshot_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)    # type: ignore[valid-type]
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)  # 残高（負債は正の値で保存し category で判断）
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
