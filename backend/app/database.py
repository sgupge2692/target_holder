import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.base import Base  # noqa: F401 – re-export for convenience

# Render 無料プランなど接続数が少ない環境に合わせたプールサイズ
# 本番VPS の場合は DB_POOL_SIZE / DB_MAX_OVERFLOW で上書き可能
_pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
_max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    pool_pre_ping=True,       # 切断された接続を自動破棄
    pool_recycle=1800,        # 30分で接続を再作成（長時間放置対策）
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
