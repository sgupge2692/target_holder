"""
シグナルエンドポイントのテスト
"""
import pytest


async def _get_token(client, email="sig@example.com", password="password123"):
    res = await client.post("/api/auth/register", json={"email": email, "password": password})
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_signals_requires_auth(client):
    res = await client.get("/api/signals/latest")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_signals_empty_for_new_user(client):
    token = await _get_token(client)
    res = await client.get("/api/signals/latest", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "signals" in data
    assert "plan" in data
    assert data["plan"] == "free"
    assert isinstance(data["signals"], list)


@pytest.mark.asyncio
async def test_accuracy_endpoint_public(client):
    """accuracy エンドポイントは認証不要"""
    res = await client.get("/api/signals/accuracy")
    assert res.status_code == 200
    data = res.json()
    assert "accuracy" in data
    assert isinstance(data["accuracy"], list)


@pytest.mark.asyncio
async def test_backtest_chart_public(client):
    """バックテストチャートは認証不要"""
    res = await client.get("/api/signals/backtest/chart?months=3")
    assert res.status_code == 200
    data = res.json()
    assert "overall" in data
    assert "monthly" in data
    assert "cumulative_return" in data


# ── 無料プランのシグナル閲覧制限（課金導線） ─────────────────────────────

async def _seed_predictions(db_session, probs):
    """銘柄ごとに最新シグナルを1件ずつ投入する。probs は up_probability のリスト。"""
    from sqlalchemy import text
    for i, p in enumerate(probs):
        await db_session.execute(text("""
            INSERT INTO predictions ("Code", "Date", up_probability, signal)
            VALUES (:code, '2026-11-06', :p, :sig)
        """), {"code": f"{1000 + i}", "p": p, "sig": "UP" if p >= 0.5 else "DOWN"})
    await db_session.commit()


async def _make_pro(db_session, email):
    from sqlalchemy import text
    await db_session.execute(
        text("UPDATE users SET plan = 'pro' WHERE email = :e"), {"e": email}
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_free_user_is_limited_to_top_signals(client, db_session):
    from app.routers.signals import FREE_SIGNAL_LIMIT
    await _seed_predictions(db_session, [0.55, 0.91, 0.62, 0.78, 0.83, 0.70])
    token = await _get_token(client, email="free@example.com")

    res = await client.get("/api/signals/latest", headers={"Authorization": f"Bearer {token}"})
    data = res.json()

    assert res.status_code == 200
    assert len(data["signals"]) == FREE_SIGNAL_LIMIT
    assert data["total_available"] == 6
    assert data["is_limited"] is True
    assert data["free_limit"] == FREE_SIGNAL_LIMIT
    # 無料枠は確度の高い順（0.91, 0.83, 0.78）
    assert [s["up_probability"] for s in data["signals"]] == [0.91, 0.83, 0.78]


@pytest.mark.asyncio
async def test_pro_user_sees_all_signals(client, db_session):
    await _seed_predictions(db_session, [0.55, 0.91, 0.62, 0.78, 0.83, 0.70])
    token = await _get_token(client, email="pro@example.com")
    await _make_pro(db_session, "pro@example.com")

    res = await client.get("/api/signals/latest", headers={"Authorization": f"Bearer {token}"})
    data = res.json()

    assert res.status_code == 200
    assert len(data["signals"]) == 6
    assert data["total_available"] == 6
    assert data["is_limited"] is False


@pytest.mark.asyncio
async def test_free_user_not_limited_when_few_signals(client, db_session):
    await _seed_predictions(db_session, [0.8, 0.7])
    token = await _get_token(client, email="few@example.com")

    res = await client.get("/api/signals/latest", headers={"Authorization": f"Bearer {token}"})
    data = res.json()

    assert len(data["signals"]) == 2
    assert data["is_limited"] is False


@pytest.mark.asyncio
async def test_signal_filter_down_sorted_by_strongest_down(client, db_session):
    """DOWN フィルタは下落確度（1 - up_probability）が高い順で、SQL エラーにならない"""
    await _seed_predictions(db_session, [0.45, 0.10, 0.30, 0.20, 0.90])
    token = await _get_token(client, email="down@example.com")

    res = await client.get(
        "/api/signals/latest?signal=DOWN", headers={"Authorization": f"Bearer {token}"}
    )
    data = res.json()

    assert res.status_code == 200
    assert data["total_available"] == 4
    assert [s["up_probability"] for s in data["signals"]] == [0.10, 0.20, 0.30]


# ── バックテスト（公開）: 対市場の集計 ───────────────────────────────────

async def _seed_backtest(db_session, days, per_day, excess, top_excess=None):
    """直近 days 日 × 毎日 per_day 件の UP シグナル。確度の高い順に 0.9, 0.89, ... を付ける"""
    from datetime import date, timedelta
    from sqlalchemy import text
    for i in range(days):
        d = (date.today() - timedelta(days=days - i)).isoformat()
        for k in range(per_day):
            ex = top_excess if (top_excess is not None and k < 3) else excess
            await db_session.execute(text("""
                INSERT INTO predictions ("Code","Date",up_probability,signal,actual_return,market_return,excess_return,is_correct)
                VALUES (:c,:d,:p,'UP',:a,0.0,:e,:ok)
            """), {"c": f"{1000 + k}", "d": d, "p": 0.9 - k * 0.001, "a": ex, "e": ex, "ok": 1 if ex > 0 else 0})
    await db_session.commit()


@pytest.mark.asyncio
async def test_backtest_cumulative_is_daily_average_not_per_signal_compounding(client, db_session):
    """
    1 日 100 件のシグナルがそれぞれ +1% でも、累積は「その日の平均 +1%」を日次で積む。
    （シグナル 1 件ごとに複利をかけると 1.01^100 のような巨大な数字になる）
    """
    await _seed_backtest(db_session, days=5, per_day=100, excess=0.01)
    res = await client.get("/api/signals/backtest/chart?months=3")
    data = res.json()

    assert res.status_code == 200
    last = data["cumulative_return"][-1]
    assert len(data["cumulative_return"]) == 5
    assert last["cumulative_return_pct"] == pytest.approx((1.01 ** 5 - 1) * 100, abs=0.01)   # ≒ 5.10%
    assert last["cumulative_return_pct"] < 10                                                  # 爆発していない


@pytest.mark.asyncio
async def test_backtest_top_k_curve_uses_highest_confidence_signals(client, db_session):
    from app.routers.signals import BACKTEST_TOP_K
    # 確度上位3件は +2%、それ以外は -1%
    await _seed_backtest(db_session, days=4, per_day=50, excess=-0.01, top_excess=0.02)
    data = (await client.get("/api/signals/backtest/chart?months=3")).json()

    last = data["cumulative_return"][-1]
    assert BACKTEST_TOP_K == 3
    assert last["top_cumulative_return_pct"] == pytest.approx((1.02 ** 4 - 1) * 100, abs=0.01)
    assert last["cumulative_return_pct"] < 0            # 全件平均はマイナス（上位だけが優位）
    assert data["meta"]["days"] == 4 and data["meta"]["top_k"] == 3
    assert data["overall"][0]["avg_excess_pct"] == pytest.approx(
        (3 * 2.0 + 47 * -1.0) / 50, abs=0.01)


@pytest.mark.asyncio
async def test_backtest_chart_excludes_old_data_and_unsettled_signals(client, db_session):
    from datetime import date, timedelta
    from sqlalchemy import text
    await _seed_backtest(db_session, days=3, per_day=5, excess=0.01)
    # 期間外（2年前）と、実績未確定（actual_return が NULL）の行
    old = (date.today() - timedelta(days=800)).isoformat()
    await db_session.execute(text(
        'INSERT INTO predictions ("Code","Date",up_probability,signal,actual_return,excess_return,is_correct) '
        "VALUES ('9001', :d, 0.9, 'UP', 0.5, 0.5, 1)"), {"d": old})
    await db_session.execute(text(
        'INSERT INTO predictions ("Code","Date",up_probability,signal) VALUES (\'9002\', :d, 0.9, \'UP\')'),
        {"d": date.today().isoformat()})
    await db_session.commit()

    data = (await client.get("/api/signals/backtest/chart?months=3")).json()
    assert len(data["cumulative_return"]) == 3                       # 期間外・未確定は含まない
    assert data["cumulative_return"][-1]["cumulative_return_pct"] == pytest.approx((1.01 ** 3 - 1) * 100, abs=0.01)


@pytest.mark.asyncio
async def test_sectors_public_and_empty(client):
    """sectors は認証不要。データが無くても空配列を返す"""
    res = await client.get("/api/signals/sectors")
    assert res.status_code == 200
    assert res.json()["sectors"] == []


@pytest.mark.asyncio
async def test_sectors_aggregates_and_filters_small_sectors(client, db_session):
    """業種ごとに平均確率・UP/DOWN件数を集計し、銘柄数が少ない業種は除く。強い順に並ぶ"""
    from sqlalchemy import text

    def stock(code, sector):
        return text("INSERT INTO listed_stocks (code, company_name, sector_code) VALUES (:c, :n, :s)"), \
            {"c": code, "n": f"銘柄{code}", "s": sector}

    def pred(code, prob, sig):
        return text('INSERT INTO predictions ("Code","Date",up_probability,signal) VALUES (:c,\'2026-11-06\',:p,:g)'), \
            {"c": code, "p": prob, "g": sig}

    rows = [
        stock("1001", "3650"), stock("1002", "3650"), stock("1003", "3650"),   # 電気機器: 強い
        stock("2001", "7050"), stock("2002", "7050"), stock("2003", "7050"),   # 銀行業: 弱い
        stock("3001", "3250"), stock("3002", "3250"),                          # 医薬品: 2件なので除外
        pred("1001", 0.60, "UP"), pred("1002", 0.56, "UP"), pred("1003", 0.52, "NEUTRAL"),
        pred("2001", 0.40, "DOWN"), pred("2002", 0.45, "NEUTRAL"), pred("2003", 0.47, "NEUTRAL"),
        pred("3001", 0.70, "UP"), pred("3002", 0.70, "UP"),
    ]
    for stmt, params in rows:
        await db_session.execute(stmt, params)
    await db_session.commit()

    res = await client.get("/api/signals/sectors")
    data = res.json()
    assert data["date"] == "2026-11-06"
    names = [s["sector_name"] for s in data["sectors"]]
    assert names == ["電気機器", "銀行業"]                 # 強い順、医薬品は除外
    top, bottom = data["sectors"]
    assert top["stock_count"] == 3 and top["up_count"] == 2 and top["down_count"] == 0
    assert abs(top["avg_up_probability"] - 0.56) < 1e-3
    assert bottom["down_count"] == 1
