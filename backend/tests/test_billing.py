"""
Billing / Stripe エンドポイントのテスト
（実際の Stripe 通信はモック）
"""
import pytest
from unittest.mock import patch, MagicMock

from app.config import settings


@pytest.fixture(autouse=True)
def stripe_settings(monkeypatch):
    """テストが環境変数(.env)の有無に左右されないよう、Stripe 設定をここで固定する"""
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")
    monkeypatch.setattr(settings, "stripe_price_id_pro", "price_monthly")
    monkeypatch.setattr(settings, "stripe_price_id_pro_yearly", "price_yearly")
    from app.routers import billing
    billing._PRICE_CACHE.clear()


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

    mock_customer = MagicMock()
    mock_customer.id = "cus_test_123"

    with patch("stripe.Customer.create", return_value=mock_customer), \
         patch("stripe.checkout.Session.create", return_value=mock_session):
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

    mock_customer = MagicMock()
    mock_customer.id = "cus_test_456"

    with patch("stripe.Customer.create", return_value=mock_customer), \
         patch("stripe.checkout.Session.create", return_value=mock_session):
        res = await client.post(
            "/api/billing/checkout",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 200
    assert res.json()["url"].startswith("https://")


# ── 年払いプラン ────────────────────────────────────────────────────────

def _checkout_mocks():
    session = MagicMock(); session.url = "https://checkout.stripe.com/c/pay/cs_test_year"
    customer = MagicMock(); customer.id = "cus_test_year"
    return session, customer


@pytest.mark.asyncio
async def test_checkout_yearly_uses_yearly_price(client):
    token = await _get_token(client, "yearly@example.com")
    session, customer = _checkout_mocks()

    with patch("stripe.Customer.create", return_value=customer), \
         patch("stripe.checkout.Session.create", return_value=session) as create:
        res = await client.post(
            "/api/billing/checkout", json={"interval": "year"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 200
    kwargs = create.call_args.kwargs
    assert kwargs["line_items"] == [{"price": "price_yearly", "quantity": 1}]
    assert kwargs["metadata"]["interval"] == "year"


@pytest.mark.asyncio
async def test_checkout_defaults_to_monthly_price(client):
    token = await _get_token(client, "monthly@example.com")
    session, customer = _checkout_mocks()

    with patch("stripe.Customer.create", return_value=customer), \
         patch("stripe.checkout.Session.create", return_value=session) as create:
        res = await client.post("/api/billing/checkout", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert create.call_args.kwargs["line_items"] == [{"price": "price_monthly", "quantity": 1}]


@pytest.mark.asyncio
async def test_checkout_yearly_rejected_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_price_id_pro_yearly", "")
    token = await _get_token(client, "noyearly@example.com")

    res = await client.post(
        "/api/billing/checkout", json={"interval": "year"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_checkout_rejects_invalid_interval(client):
    token = await _get_token(client, "badinterval@example.com")
    res = await client.post(
        "/api/billing/checkout", json={"interval": "week"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_checkout_rejected_for_existing_pro_user(client, db_session):
    from sqlalchemy import text
    token = await _get_token(client, "alreadypro@example.com")
    await db_session.execute(text("UPDATE users SET plan = 'pro' WHERE email = 'alreadypro@example.com'"))
    await db_session.commit()

    with patch("stripe.checkout.Session.create") as create:
        res = await client.post("/api/billing/checkout", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400
    create.assert_not_called()                       # 二重サブスクリプションを作らない


@pytest.mark.asyncio
async def test_plans_returns_amounts_from_stripe(client):
    def fake_retrieve(price_id):
        m = MagicMock(); m.unit_amount = {"price_monthly": 2980, "price_yearly": 29800}[price_id]
        return m

    with patch("stripe.Price.retrieve", side_effect=fake_retrieve):
        res = await client.get("/api/billing/plans")     # 認証不要

    assert res.status_code == 200
    assert res.json() == {"yearly_available": True, "monthly_amount": 2980, "yearly_amount": 29800}


@pytest.mark.asyncio
async def test_plans_without_yearly_or_stripe_failure(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_price_id_pro_yearly", "")
    with patch("stripe.Price.retrieve", side_effect=RuntimeError("stripe down")):
        res = await client.get("/api/billing/plans")

    assert res.status_code == 200
    assert res.json() == {"yearly_available": False, "monthly_amount": None, "yearly_amount": None}
