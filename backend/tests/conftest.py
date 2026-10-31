"""
pytest 設定 — インメモリ SQLite でテスト用DBを構築
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.base import Base
from app.models import User  # テーブル登録
from app.database import get_db
from app.main import app
from app.limiter import limiter

# ── インメモリ SQLite エンジン ────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="function")
async def test_engine():
    from sqlalchemy import text as sa_text
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Raw SQL テーブル（J-Quantsからのデータ、モデルなし）
        await conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS listed_stocks (
                code TEXT PRIMARY KEY,
                company_name TEXT,
                sector TEXT,
                market TEXT
            )
        """))
        await conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                "Code" TEXT,
                "Date" TEXT,
                up_probability REAL,
                signal TEXT,
                predicted_at TEXT,
                explanation TEXT,
                key_factors TEXT,
                actual_return REAL,
                is_correct INTEGER
            )
        """))
        await conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS daily_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                "Code" TEXT,
                "Date" TEXT,
                "Close" REAL,
                "AdjustmentClose" REAL
            )
        """))
        await conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                "Code" TEXT,
                "Date" TEXT
            )
        """))
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(test_engine):
    """FastAPI テストクライアント (DB はインメモリ SQLite に差し替え)"""
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # テスト中はレート制限を無効化（各テストが独立して動作するため）
    limiter.enabled = False

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    limiter.enabled = True
    app.dependency_overrides.clear()
