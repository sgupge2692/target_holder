"""
通知設定エンドポイントのテスト
"""
import pytest


async def _register_and_token(client, email, plan="free"):
    res = await client.post("/api/auth/register", json={"email": email, "password": "pass1234"})
    token = res.json()["access_token"]

    if plan == "pro":
        # DBを直接更新してProに変える
        from sqlalchemy import text
        # conftest の db_session は別fixture なのでここでは割愛
        pass

    return token


@pytest.mark.asyncio
async def test_get_notification_settings_defaults(client):
    res = await client.post("/api/auth/register", json={
        "email": "notif@example.com", "password": "pass1234"
    })
    token = res.json()["access_token"]

    r = await client.get(
        "/api/notifications/settings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["email_signal_alert"] is False
    assert data["email_unsubscribed"] is False


@pytest.mark.asyncio
async def test_free_user_cannot_enable_signal_alert(client):
    """無料ユーザーはメールアラートを有効にできない"""
    res = await client.post("/api/auth/register", json={
        "email": "free_notif@example.com", "password": "pass1234"
    })
    token = res.json()["access_token"]

    r = await client.patch(
        "/api/notifications/settings",
        json={"email_signal_alert": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_unsubscribe_works_for_free_user(client):
    """配信停止は無料ユーザーでも可能"""
    res = await client.post("/api/auth/register", json={
        "email": "unsub@example.com", "password": "pass1234"
    })
    token = res.json()["access_token"]

    r = await client.patch(
        "/api/notifications/settings",
        json={"email_unsubscribed": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["email_unsubscribed"] is True
