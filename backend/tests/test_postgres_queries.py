"""
PostgreSQL 実機でのクエリ検証

通常のテストはインメモリ SQLite で動くため、PostgreSQL に無い関数（date('now', ...) や
DATE 列への substr など）を使っていても通ってしまう。実際に過去、公開バックテスト API が
本番(PostgreSQL)でだけ 500 になる不具合があった。ここでは生 SQL を使う API を PostgreSQL で流す。

実行条件: 環境変数 TEST_POSTGRES_URL が設定されているときだけ動く（未設定ならスキップ）。
  例: TEST_POSTGRES_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/test
  ※ 接続先の public スキーマは各テストの前に作り直される。本番DBを指定しないこと。
CI では backend-test-postgres ジョブ（postgres サービス）が設定する。
"""
import os
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

PG_URL = os.getenv("TEST_POSTGRES_URL", "")

pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL 未設定（PostgreSQL 実機テストはスキップ）")

# db/init.sql の predictions / listed_stocks（TimescaleDB 部分を除く）と
# Alembic 0004（explanation, key_factors）・0011（market_return, excess_return）を反映したスキーマ
RAW_SCHEMA = """
CREATE TABLE listed_stocks (
    code VARCHAR(10) PRIMARY KEY,
    company_name VARCHAR(200),
    market_code VARCHAR(10),
    sector_code VARCHAR(10),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    "Code" VARCHAR(10) NOT NULL,
    "Date" DATE NOT NULL,
    up_probability NUMERIC NOT NULL,
    signal VARCHAR(10) NOT NULL,
    predicted_at TIMESTAMP DEFAULT NOW(),
    actual_return NUMERIC,
    market_return NUMERIC,
    excess_return NUMERIC,
    is_correct BOOLEAN,
    explanation TEXT,
    key_factors TEXT
);
"""


@pytest_asyncio.fixture
async def pg_engine():
    from app.base import Base
    from app import models  # noqa: F401  (テーブル登録)

    engine = create_async_engine(PG_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)
        for stmt in [s.strip() for s in RAW_SCHEMA.split(";") if s.strip()]:
            await conn.execute(text(stmt))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_client(pg_engine):
    from app.main import app
    from app.database import get_db
    from app.limiter import limiter

    factory = async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    limiter.enabled = False
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ac.session_factory = factory
        yield ac
    limiter.enabled = True
    app.dependency_overrides.clear()


async def _seed(client, days=10, per_day=12):
    """直近 days 日 × per_day 銘柄の UP シグナル（実績つき）と、最新日の DOWN を 1 件投入"""
    async with client.session_factory() as s:
        for k in range(per_day):
            await s.execute(text("INSERT INTO listed_stocks (code, company_name) VALUES (:c, :n)"),
                            {"c": f"{1000 + k}", "n": f"銘柄{k}"})
        for i in range(days):
            d = date.today() - timedelta(days=days - i)
            for k in range(per_day):
                ex = 0.01 if k < 3 else -0.002
                await s.execute(text("""
                    INSERT INTO predictions ("Code","Date",up_probability,signal,actual_return,
                                             market_return,excess_return,is_correct)
                    VALUES (:c,:d,:p,'UP',:a,0.001,:e,:ok)
                """), {"c": f"{1000 + k}", "d": d, "p": 0.9 - k * 0.01, "a": ex + 0.001, "e": ex, "ok": ex > 0})
        await s.execute(text("""
            INSERT INTO predictions ("Code","Date",up_probability,signal)
            VALUES ('1000', :d, 0.2, 'DOWN')
        """), {"d": date.today()})
        await s.commit()


async def _register(client, email):
    res = await client.post("/api/auth/register", json={"email": email, "password": "pass1234"})
    assert res.status_code == 201
    return res.json()["access_token"]


async def test_backtest_chart_runs_on_postgres(pg_client):
    await _seed(pg_client)
    res = await pg_client.get("/api/signals/backtest/chart?months=3")

    assert res.status_code == 200
    data = res.json()
    assert len(data["cumulative_return"]) == 10
    # 上位3件は毎日 +1%、全件平均は (3*1% + 9*-0.2%) / 12 = 0.1%
    last = data["cumulative_return"][-1]
    assert last["top_cumulative_return_pct"] == pytest.approx((1.01 ** 10 - 1) * 100, abs=0.01)
    assert last["cumulative_return_pct"] == pytest.approx((1.001 ** 10 - 1) * 100, abs=0.01)
    assert data["meta"]["days"] == 10
    # NUMERIC が Decimal のまま JSON に出ていない（数値として返る）
    assert isinstance(data["overall"][0]["accuracy_pct"], (int, float))
    assert isinstance(data["overall"][0]["avg_excess_pct"], (int, float))
    assert isinstance(data["monthly"][0]["up_accuracy"], (int, float))


async def test_accuracy_runs_on_postgres(pg_client):
    await _seed(pg_client)
    res = await pg_client.get("/api/signals/accuracy")
    assert res.status_code == 200
    row = res.json()["accuracy"][0]
    assert row["signal"] == "UP"
    assert isinstance(row["accuracy_pct"], (int, float))
    assert isinstance(row["avg_return_pct"], (int, float))


async def test_latest_limits_free_users_on_postgres(pg_client):
    await _seed(pg_client)
    token = await _register(pg_client, "free@example.com")
    res = await pg_client.get("/api/signals/latest", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3 and data["is_limited"] is True
    assert data["total_available"] == 12
    probs = [float(s["up_probability"]) for s in data["signals"]]
    assert probs == sorted(probs, reverse=True)


async def test_latest_signal_filter_and_pro_on_postgres(pg_client):
    await _seed(pg_client)
    token = await _register(pg_client, "pro@example.com")
    async with pg_client.session_factory() as s:
        await s.execute(text("UPDATE users SET plan = 'pro' WHERE email = 'pro@example.com'"))
        await s.commit()
    headers = {"Authorization": f"Bearer {token}"}

    # signal フィルタ指定時に SQL エラーにならない（WHERE の二重指定バグの再発防止）
    down = await pg_client.get("/api/signals/latest?signal=DOWN", headers=headers)
    assert down.status_code == 200 and down.json()["total"] == 1

    all_ = await pg_client.get("/api/signals/latest", headers=headers)
    assert all_.json()["total"] == 12 and all_.json()["is_limited"] is False


async def test_history_runs_on_postgres(pg_client):
    await _seed(pg_client)
    token = await _register(pg_client, "hist@example.com")
    res = await pg_client.get("/api/signals/history/1000", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.json()["history"]) >= 1


async def test_sectors_runs_on_postgres(pg_client):
    """業種別ヒートマップが PostgreSQL で動く（sector_code は init.sql の実スキーマ）"""
    async with pg_client.session_factory() as s:
        for code, sector in [("1001", "3650"), ("1002", "3650"), ("1003", "3650"), ("2001", "7050")]:
            await s.execute(text("INSERT INTO listed_stocks (code, company_name, sector_code) VALUES (:c,:n,:s)"),
                            {"c": code, "n": f"銘柄{code}", "s": sector})
        for code, prob, sig in [("1001", 0.6, "UP"), ("1002", 0.55, "UP"), ("1003", 0.5, "NEUTRAL"), ("2001", 0.4, "DOWN")]:
            await s.execute(text('INSERT INTO predictions ("Code","Date",up_probability,signal) VALUES (:c,:d,:p,:g)'),
                            {"c": code, "d": date.today(), "p": prob, "g": sig})
        await s.commit()

    res = await pg_client.get("/api/signals/sectors")
    assert res.status_code == 200
    data = res.json()
    assert [x["sector_name"] for x in data["sectors"]] == ["電気機器"]     # 銀行業は1銘柄なので除外
    assert isinstance(data["sectors"][0]["avg_up_probability"], float)
    assert data["date"] == date.today().isoformat()


async def test_latest_change_from_previous_runs_on_postgres(pg_client):
    """前回予測との差（相関サブクエリ）が PostgreSQL で動き、値が数値で返る"""
    await _seed(pg_client, days=3, per_day=4)
    token = await _register(pg_client, "chg-pg@example.com")
    # 無料プランは確度上位3件だけ見えるので、DOWN で絞って 1000 を確実に含める
    res = await pg_client.get("/api/signals/latest?signal=DOWN", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    s = {x["Code"]: x for x in res.json()["signals"]}["1000"]
    # 最新は DOWN(0.2)、前日は UP(0.9)
    assert s["signal"] == "DOWN" and s["prev_signal"] == "UP"
    assert s["signal_changed"] is True
    assert s["prob_change_pt"] == pytest.approx(-70.0, abs=0.1)
    assert isinstance(s["prob_change_pt"], float)
