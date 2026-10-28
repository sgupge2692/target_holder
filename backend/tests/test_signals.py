"""
シグナルエンドポイントのテスト
"""
import pytest


async def _get_token(client, email="sig@example.com", password="password123"):
    res = await client.post("/api/auth/register", json={"email": email, "password": password})
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_signals_requires_auth(client):
    res = await client.get("/api/signals/")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_signals_empty_for_new_user(client):
    token = await _get_token(client)
    res = await client.get("/api/signals/", headers={"Authorization": f"Bearer {token}"})
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
