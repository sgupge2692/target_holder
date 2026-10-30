"""
Billing / Stripe エンドポイントのテスト
（実際の Stripe 通信はモック）
"""
import pytest
from unittest.mock import patch, MagicMock


async def _get_token(client, email="billing@example.com"):
    res = await client.post("/api/auth/register", json={
        "email": email, "password": "pass1234"
    })
    assert res.status_code == 201
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_checkout_requires_auth(client):
    res = await client.post("/api/billing/checkout")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_checkout_creates_stripe_session(client):
    """Stripe をモックしてチェックアウトURLが返ることを確認"""
    token = await _get_token(client, "checkout@example.com")

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/test_session_url"

    with patch("stripe.checkout.Session.create", return_value=mock_session):
        res = await client.post(
            "/api/billing/checkout",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 200
    data = res.json()
    assert "url" in data
    assert "stripe.com" in data["url"]


@pytest.mark.asyncio
async def test_portal_requires_pro(client):
    """無料ユーザーはポータルを開けない"""
    token = await _get_token(client, "portal_free@example.com")
    res = await client.post(
        "/api/billing/portal",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code in (400, 403)


@pytest.mark.asyncio
async def test_subscription_info_free_user(client):
    token = await _get_token(client, "sub_free@example.com")
    res = await client.get(
        "/api/billing/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )
    # 無料ユーザーは subscription 情報なし → 404 or plan=free を返す
    assert res.status_code in (200, 404)
    if res.status_code == 200:
        data = res.json()
        assert data.get("plan") in ("free", None)


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_400(client):
    """不正な署名の Webhook は 400 を返す"""
    res = await client.post(
        "/api/billing/webhook",
        content=b'{"type": "checkout.session.completed"}',
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "invalid_sig",
        },
    )
    assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_checkout_returns_url_for_free_user(client):
    """無料ユーザーがアップグレードURLを取得できる"""
    token = await _get_token(client, "upgrade@example.com")

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/c/pay/cs_test_xxx"

    with patch("stripe.checkout.Session.create", return_value=mock_session):
        res = await client.post(
            "/api/billing/checkout",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 200
    assert res.json()["url"].startswith("https://")
