"""
認証エンドポイントのテスト
"""
import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    res = await client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "password123",
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "password123"}
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/register", json=payload)
    assert res.status_code == 400
    assert "既に登録" in res.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client):
    # 先に登録
    await client.post("/api/auth/register", json={
        "email": "login@example.com",
        "password": "password123",
    })
    # フォーム形式でログイン
    res = await client.post("/api/auth/login", data={
        "username": "login@example.com",
        "password": "password123",
    })
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={
        "email": "wrong@example.com",
        "password": "password123",
    })
    res = await client.post("/api/auth/login", data={
        "username": "wrong@example.com",
        "password": "wrongpassword",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint(client):
    # 登録してトークン取得
    reg = await client.post("/api/auth/register", json={
        "email": "me@example.com",
        "password": "password123",
    })
    token = reg.json()["access_token"]

    res = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "me@example.com"
    assert data["plan"] == "free"


@pytest.mark.asyncio
async def test_me_unauthorized(client):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_password_reset_request_returns_202(client):
    """ユーザーが存在しなくても 202 を返す（情報漏洩防止）"""
    res = await client.post(
        "/api/auth/password-reset/request",
        json={"email": "nobody@example.com"},
    )
    assert res.status_code == 202


@pytest.mark.asyncio
async def test_password_reset_invalid_token(client):
    res = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": "invalidtoken", "new_password": "newpassword123"},
    )
    assert res.status_code == 400
