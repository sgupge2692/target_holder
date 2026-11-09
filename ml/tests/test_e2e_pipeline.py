"""
パイプライン全体の E2E スモークテスト（PostgreSQL 実機）

合成データ → 特徴量 → リーク検査 → 学習 → 予測 → 実績記録 → API / メール / X 投稿の取得処理
を cron と同じ形（CLI をサブプロセスで実行）で通し、工程間の列名・型・受け渡しの食い違いを見つける。
精度を測るテストではない（合成データなので精度には意味がない）。

実行:
  TEST_POSTGRES_URL=postgresql://user@localhost:5432/dbname pytest ml/tests/test_e2e_pipeline.py
  ※ 対象 DB の public スキーマを作り直す。本番 DB を指さないこと。
"""
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, text

PG_URL = os.getenv("TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL 未設定（E2E は PostgreSQL 実機が必要）")

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "ml" / "pipeline"

N_STOCKS = 60
N_DAYS = 420            # 営業日。ウォークフォワードCV（5分割）に足りる長さ
EXTRA_DAYS = 3          # 予測後に追加して、実績記録（backtest）を試す日数
SECTORS = ["3650", "7050", "3250", "5250", "3700", "6100"]


def _sync_url(url: str) -> str:
    # ドライバを明示する（SQLAlchemy 2.1 は "postgresql://" を psycopg3 に解決するが、ML コンテナは psycopg2）
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


def _schema_sql() -> str:
    """db/init.sql から TimescaleDB 依存の部分を除き、Alembic 0004 の列を足したもの"""
    sql = (ROOT / "db" / "init.sql").read_text(encoding="utf-8")
    kept = [
        ln for ln in sql.splitlines()
        if "CREATE EXTENSION" not in ln and "create_hypertable" not in ln
    ]
    return "\n".join(kept) + "\nALTER TABLE predictions ADD COLUMN IF NOT EXISTS explanation TEXT;" \
                             "\nALTER TABLE predictions ADD COLUMN IF NOT EXISTS key_factors TEXT;"


def _synthetic_quotes(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """市場共通の動き + 業種の動き + 銘柄固有の動き。直近の値動きが翌日にわずかに効く弱い構造を入れる。"""
    rng = np.random.default_rng(42)
    market = rng.normal(0.0003, 0.008, len(dates))
    sector_move = {s: rng.normal(0, 0.005, len(dates)) for s in SECTORS}
    rows = []
    for k in range(N_STOCKS):
        code = f"{1300 + k * 7}"
        sector = SECTORS[k % len(SECTORS)]
        idio = rng.normal(0, 0.012, len(dates))
        ret = market + sector_move[sector] + idio
        ret[1:] += 0.05 * ret[:-1]              # 弱いモメンタム
        close = 1000 * (1 + k % 5) * np.cumprod(1 + ret)
        for i, d in enumerate(dates):
            c = float(close[i])
            hi, lo = c * (1 + abs(rng.normal(0, 0.006))), c * (1 - abs(rng.normal(0, 0.006)))
            rows.append({
                "Code": code, "Date": d.date(), "Open": round((hi + lo) / 2, 1), "High": round(hi, 1),
                "Low": round(lo, 1), "Close": round(c, 1), "Volume": int(rng.integers(100_000, 5_000_000)),
                "AdjustmentClose": round(c, 1), "sector": sector, "name": f"合成銘柄{k}",
            })
    return pd.DataFrame(rows)


def _run(script: str, args: list[str], env: dict, timeout: int = 900) -> str:
    proc = subprocess.run(
        [sys.executable, str(PIPELINE / script), *args],
        cwd=str(ROOT / "ml"), env=env, capture_output=True, text=True, timeout=timeout,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"{script} が失敗しました (exit {proc.returncode})\n{out[-3000:]}"
    return out


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    url = _sync_url(PG_URL)
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        for stmt in [s.strip() for s in _schema_sql().split(";") if s.strip()]:
            conn.execute(text(stmt))

    # 最後の営業日を「今日」の少し前にそろえ、EXTRA_DAYS 分は予測後に追加する
    all_dates = pd.bdate_range(end=pd.Timestamp(date.today()) - pd.offsets.BDay(1), periods=N_DAYS + EXTRA_DAYS)
    quotes = _synthetic_quotes(all_dates)
    base_dates = set(d.date() for d in all_dates[:N_DAYS])

    stocks = quotes.drop_duplicates("Code")[["Code", "name", "sector"]]
    with engine.begin() as conn:
        for r in stocks.itertuples():
            conn.execute(text("INSERT INTO listed_stocks (code, company_name, sector_code) VALUES (:c,:n,:s)"),
                         {"c": r.Code, "n": r.name, "s": r.sector})
    cols = ["Code", "Date", "Open", "High", "Low", "Close", "Volume", "AdjustmentClose"]
    quotes[quotes["Date"].isin(base_dates)][cols].to_sql("daily_quotes", engine, if_exists="append", index=False)

    env = {
        **os.environ,
        "DATABASE_URL": url,
        "MODEL_DIR": str(tmp_path_factory.mktemp("models")),
        "OPENAI_API_KEY": "", "NEWS_SENTIMENT": "false",
        "PYTHONPATH": str(ROOT / "ml"),
        "MIN_SIGNALS_PER_SIDE": "10",
    }
    return {"engine": engine, "env": env, "quotes": quotes, "base_dates": base_dates,
            "cols": cols, "last_date": max(base_dates)}


def test_01_feature_engineering(world):
    out = _run("feature_engineering.py", [], world["env"])
    with world["engine"].connect() as c:
        n, last = c.execute(text('SELECT COUNT(*), MAX("Date")::date FROM features')).one()
        has = c.execute(text("SELECT COUNT(*) FROM information_schema.columns "
                             "WHERE table_name='features' AND column_name IN ('label_excess','excess_return','market_return')")).scalar()
    assert n > N_STOCKS * 300, out
    assert has == 3
    assert last == world["last_date"]          # 最新日の特徴量が残っている（予測に必要）


def test_02_sanity_checks_pass_on_clean_data(world):
    _run("sanity_checks.py", [], world["env"])


def test_03_train_ensemble_saves_models(world):
    out = _run("train.py", ["--mode", "ensemble"], world["env"], timeout=1500)
    models = Path(world["env"]["MODEL_DIR"])
    for name in ["lgbm_model.pkl", "xgb_model.pkl", "scaler.pkl", "feature_cols.pkl", "ensemble_weights.pkl", "calibrator.pkl"]:
        assert (models / name).exists(), f"{name} が保存されていません\n{out[-2000:]}"

    # 合成データの精度は意味を持たないが、「リークで高すぎる」「壊れて低すぎる」は検出できる。
    # （旧 CV はノイズだけのデータで AUC 0.88 を出していた）
    import joblib
    metrics = joblib.load(models / "metrics.pkl")
    assert 0.45 <= metrics["ensemble_auc"] <= 0.62, f"ensemble AUC が範囲外: {metrics}"
    assert metrics["ece_calibrated"] <= metrics["ece_raw"] + 0.01, f"校正で悪化している: {metrics}"


def test_04_predict_saves_signals_for_latest_day(world):
    out = _run("predict.py", [], world["env"])
    with world["engine"].connect() as c:
        rows = c.execute(text('SELECT "Date", signal, COUNT(*) FROM predictions GROUP BY 1,2')).fetchall()
    assert {r[0] for r in rows} == {world["last_date"]}, out
    by_sig = {r[1]: r[2] for r in rows}
    assert by_sig.get("UP", 0) >= 10 and by_sig.get("DOWN", 0) >= 10, by_sig   # 校正後でも各サイド最低件数
    assert sum(by_sig.values()) == N_STOCKS, by_sig                           # NEUTRAL も含め全銘柄を保存する


def test_05_backtest_records_actual_returns(world):
    """予測の翌営業日以降の株価を追加し、実績（超過リターンと的中）が記録されること"""
    extra = world["quotes"][~world["quotes"]["Date"].isin(world["base_dates"])]
    extra[world["cols"]].to_sql("daily_quotes", world["engine"], if_exists="append", index=False)
    out = _run("backtest.py", ["--date", world["last_date"].isoformat()], world["env"])
    with world["engine"].connect() as c:
        n, ok, ex, judged = c.execute(text(
            "SELECT COUNT(*), COUNT(is_correct), COUNT(excess_return), "
            "COUNT(*) FILTER (WHERE signal IN ('UP','DOWN')) "
            "FROM predictions WHERE actual_return IS NOT NULL"
        )).one()
    assert n == N_STOCKS and ex == n, out        # 全銘柄の実績を記録
    assert ok == judged > 0, out                 # 的中判定は UP / DOWN のみ（中立は判定しない）


def test_06_api_and_scripts_read_pipeline_output(world):
    """パイプラインが書いたデータを、API・日次メール・X 投稿の取得処理が実際に読めること"""
    import asyncio
    sys.path.insert(0, str(ROOT / "backend"))
    sys.path.insert(0, str(ROOT))
    os.environ["DATABASE_URL"] = world["env"]["DATABASE_URL"].replace("postgresql+psycopg2://", "postgresql+asyncpg://")

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool
    from sqlalchemy import text
    from app.base import Base
    from app import models  # noqa: F401
    from app.database import get_db
    from app.limiter import limiter
    from app.main import app
    from scripts.send_daily_signals import fetch_today_signals, fetch_accuracy, fetch_watch_changes

    async def go():
        eng = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async def override():
            async with AsyncSession(eng, expire_on_commit=False) as s:
                yield s

        app.dependency_overrides[get_db] = override
        limiter.enabled = False
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                res = await client.post("/api/auth/register", json={"email": "e2e@example.com", "password": "pass1234"})
                headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

                latest = (await client.get("/api/signals/latest", headers=headers)).json()
                assert latest["total_available"] >= 20 and latest["total"] == latest["free_limit"]
                top = latest["signals"][0]["Code"]

                chart = await client.get("/api/signals/backtest/chart?months=3")
                assert chart.status_code == 200 and chart.json()["overall"], chart.text

                assert all(x["signal"] in ("UP", "DOWN") for x in latest["signals"])   # 一覧に中立は出ない

                sectors = (await client.get("/api/signals/sectors")).json()
                assert len(sectors["sectors"]) == len(SECTORS)
                assert sum(x["stock_count"] for x in sectors["sectors"]) == N_STOCKS   # 全銘柄が集計対象

                peers = await client.get(f"/api/stocks/{top}/peers", headers=headers)
                assert peers.status_code == 200 and peers.json()["rank"] is not None

                acc = (await client.get("/api/signals/accuracy")).json()["accuracy"]
                assert {r["signal"] for r in acc} <= {"UP", "DOWN"}                      # 的中率に中立は混ざらない

                async with AsyncSession(eng) as s:                                         # CSV は Pro 専用
                    await s.execute(text("UPDATE users SET plan='pro' WHERE email='e2e@example.com'"))
                    await s.commit()
                csv_res = await client.get("/api/signals/export/csv?days=60", headers=headers)
                assert csv_res.status_code == 200 and "コード" in csv_res.text, csv_res.text[:300]

                hist = await client.get(f"/api/signals/history/{top}", headers=headers)
                assert hist.status_code == 200 and hist.json()["history"]

            async with AsyncSession(eng) as s:
                assert await fetch_today_signals(s, limit=5)
                await fetch_accuracy(s)
                await fetch_watch_changes(s, world["last_date"])
        finally:
            app.dependency_overrides.clear()
            limiter.enabled = True
            await eng.dispose()

    asyncio.run(go())
