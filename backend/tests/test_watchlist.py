"""
ウォッチリストエンドポイントのテスト
"""
import pytest


async def _get_token(client, email="watch@example.com", password="pass1234"):
    res = await client.post("/api/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201, res.text
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_watchlist_requires_auth(client):
    res = await client.get("/api/watchlist")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_watchlist_empty_initially(client):
    token = await _get_token(client, "wl_empty@example.com")
    res = await client.get("/api/watchlist", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "watchlist" in data
    assert data["watchlist"] == []
    assert "plan" in data


@pytest.mark.asyncio
async def test_add_and_get_watchlist(client):
    token = await _get_token(client, "wl_add@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 追加
    res = await client.post("/api/watchlist/7203", headers=headers)
    assert res.status_code in (200, 201)

    # 一覧確認
    res = await client.get("/api/watchlist", headers=headers)
    codes = [item["code"] for item in res.json()["watchlist"]]
    assert "7203" in codes


@pytest.mark.asyncio
async def test_add_duplicate_is_idempotent(client):
    """同じ銘柄を2回追加してもエラーにならない"""
    token = await _get_token(client, "wl_dup@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    await client.post("/api/watchlist/9984", headers=headers)
    res = await client.post("/api/watchlist/9984", headers=headers)
    assert res.status_code in (200, 201, 409)  # 409 Conflict も許容


@pytest.mark.asyncio
async def test_remove_from_watchlist(client):
    token = await _get_token(client, "wl_remove@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 追加 → 削除
    await client.post("/api/watchlist/6758", headers=headers)
    res = await client.delete("/api/watchlist/6758", headers=headers)
    assert res.status_code == 200

    # 一覧で消えている
    res = await client.get("/api/watchlist", headers=headers)
    codes = [item["code"] for item in res.json()["watchlist"]]
    assert "6758" not in codes


@pytest.mark.asyncio
async def test_remove_nonexistent_returns_404(client):
    token = await _get_token(client, "wl_rm404@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.delete("/api/watchlist/0000", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_watchlist_status_endpoint(client):
    token = await _get_token(client, "wl_status@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 未登録
    res = await client.get("/api/watchlist/7203/status", headers=headers)
    assert res.status_code == 200
    assert res.json()["watched"] is False

    # 登録後
    await client.post("/api/watchlist/7203", headers=headers)
    res = await client.get("/api/watchlist/7203/status", headers=headers)
    assert res.json()["watched"] is True


@pytest.mark.asyncio
async def test_free_plan_limit(client):
    """無料ユーザーは30件上限（31件目でエラー）"""
    token = await _get_token(client, "wl_limit@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 30件追加（コードを 1000〜1029 で仮定）
    for i in range(30):
        code = str(1000 + i)
        await client.post(f"/api/watchlist/{code}", headers=headers)

    # 31件目
    res = await client.post("/api/watchlist/9999", headers=headers)
    # 400 / 403 / 429 でウォッチリスト上限エラー
    assert res.status_code in (400, 403, 429)
