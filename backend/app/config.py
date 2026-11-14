import secrets
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://stock:stock@db:5432/stockdb"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_pro: str = ""
    stripe_price_id_pro_yearly: str = ""   # 年払い（未設定なら年払いは無効）

    openai_api_key: str = ""

    # 本番 URL（Stripe リダイレクト先など）
    frontend_url: str = "http://localhost:3000"

    # オーナー（作成者）メールアドレス: カンマ区切りで複数指定可
    # 例: OWNER_EMAILS=you@example.com,partner@example.com
    owner_emails: str = ""

    @property
    def owner_email_set(self) -> set[str]:
        """オーナーメールアドレスを小文字 set で返す"""
        return {e.strip().lower() for e in self.owner_emails.split(",") if e.strip()}

    class Config:
        env_file = ".env"
        extra = "ignore"

    def validate_secrets(self) -> None:
        """本番環境でデフォルト値のままの場合は起動を拒否する"""
        env = __import__("os").getenv("ENV", "development")
        if env == "production":
            if self.jwt_secret == "change-me-in-production":
                raise RuntimeError(
                    "本番環境では JWT_SECRET を必ず変更してください。"
                    f"例: JWT_SECRET={secrets.token_hex(32)}"
                )
            if len(self.jwt_secret) < 32:
                raise RuntimeError("JWT_SECRET は32文字以上にしてください")


settings = Settings()
settings.validate_secrets()
