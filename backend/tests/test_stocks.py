"""
銘柄エンドポイントのテスト（同業種の比較）
"""
import pytest
from sqlalchemy import text


async def _register(client, email):
    res = await client.post("/api/auth/register", json={"email": email, "password": "pass1234"})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def _seed_sector(db_session):
    stocks = [("1001", "A社", "3650"), ("1002", "B社", "3650"), ("1003", "C社", "3650"),
              ("2001", "D社", "7050"), ("3001", "E社", None)]
    for code, name, sector in stocks:
        await db_session.execute(
            text("INSERT INTO listed_stocks (code, company_name, sector_code) VALUES (:c,:n,:s)"),
            {"c": code, "n": name, "s": sector},
        )
    for code, prob, sig in [("1001", 0.52, "NEUTRAL"), ("1002", 0.61, "UP"), ("1003", 0.40, "DOWN"), ("2001", 0.7, "UP")]:
        await db_session.execute(
            text('INSERT INTO predictions ("Code","Date",up_probability,signal) VALUES (:c,\'2026-11-06\',:p,:g)'),
            {"c": code, "p": prob, "g": sig},
        )
    await db_session.commit()


@pytest.mark.asyncio
async def test_peers_requires_auth(client):
    assert (await client.get("/api/stocks/1001/peers")).status_code == 401


@pytest.mark.asyncio
async def test_peers_unknown_stock_404(client):
    headers = await _register(client, "peer404@example.com")
    assert (await client.get("/api/stocks/9999/peers", headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_peers_free_gets_rank_but_no_peer_list(client, db_session):
    await _seed_sector(db_session)
    headers = await _register(client, "peer-free@example.com")
    data = (await client.get("/api/stocks/1001/peers", headers=headers)).json()
    assert data["sector_name"] == "電気機器"
    assert data["stock_count"] == 3 and data["rank"] == 2          # 0.61 > 0.52 > 0.40
    assert data["avg_up_probability"] == pytest.approx((0.52 + 0.61 + 0.40) / 3, abs=1e-3)
    assert data["peers"] == [] and data["peers_locked"] is True    # 個別銘柄は有料


@pytest.mark.asyncio
async def test_peers_pro_gets_sorted_peer_list_without_self(client, db_session):
    await _seed_sector(db_session)
    headers = await _register(client, "peer-pro@example.com")
    await db_session.execute(text("UPDATE users SET plan = 'pro' WHERE email = 'peer-pro@example.com'"))
    await db_session.commit()
    data = (await client.get("/api/stocks/1001/peers", headers=headers)).json()
    assert data["peers_locked"] is False
    assert [p["code"] for p in data["peers"]] == ["1002", "1003"]  # 自分は除く・確率の高い順


@pytest.mark.asyncio
async def test_peers_without_sector_or_prediction(client, db_session):
    await _seed_sector(db_session)
    headers = await _register(client, "peer-none@example.com")
    data = (await client.get("/api/stocks/3001/peers", headers=headers)).json()   # 業種コード無し
    assert data["rank"] is None and data["stock_count"] == 0 and data["peers"] == []
