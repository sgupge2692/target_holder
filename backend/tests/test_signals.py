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
