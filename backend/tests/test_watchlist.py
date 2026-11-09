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


@pytest.mark.asyncio
async def test_watchlist_shows_change_from_previous(client, db_session):
    """前回からの確率変化とシグナル反転が付く。前回が無い銘柄は None"""
    from sqlalchemy import text

    token = await _get_token(client, "wl_chg@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/api/watchlist/7203", headers=headers)
    await client.post("/api/watchlist/9984", headers=headers)

    rows = [
        ("7203", "2026-11-05", 0.45, "NEUTRAL"),
        ("7203", "2026-11-06", 0.61, "UP"),
        ("9984", "2026-11-06", 0.58, "UP"),
    ]
    for code, d, p, sg in rows:
        await db_session.execute(
            text('INSERT INTO predictions ("Code","Date",up_probability,signal,predicted_at) VALUES (:c,:d,:p,:s,:d)'),
            {"c": code, "d": d, "p": p, "s": sg},
        )
    await db_session.commit()

    res = await client.get("/api/watchlist", headers=headers)
    by_code = {x["code"]: x for x in res.json()["watchlist"]}
    a, b = by_code["7203"], by_code["9984"]
    assert a["signal"] == "UP" and a["prev_signal"] == "NEUTRAL" and a["signal_changed"] is True
    assert a["prob_change_pt"] == 16.0
    assert b["prob_change_pt"] is None and b["signal_changed"] is None
