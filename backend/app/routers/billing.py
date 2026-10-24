"""
課金エンドポイント (Stripe)
- POST /api/billing/checkout  : Stripe Checkout セッション作成
- POST /api/billing/portal    : 顧客ポータル URL 取得
- POST /api/billing/webhook   : Stripe Webhook 受信
"""
import stripe
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/api/billing", tags=["billing"])

stripe.api_key = settings.stripe_secret_key


# ── スキーマ ──────────────────────────────────────────────────

class CheckoutResponse(BaseModel):
    url: str


class PortalResponse(BaseModel):
    url: str


# ── ヘルパー ──────────────────────────────────────────────────

async def _get_or_create_customer(user: User, db: AsyncSession) -> str:
    """Stripe 顧客IDを取得 or 新規作成してDBに保存"""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = stripe.Customer.create(email=user.email, metadata={"user_id": str(user.id)})
    user.stripe_customer_id = customer.id
    await db.commit()
    return customer.id


# ── エンドポイント ────────────────────────────────────────────

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stripe Checkout セッションを作成して支払いページ URL を返す"""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe 未設定")

    customer_id = await _get_or_create_customer(current_user, db)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": settings.stripe_price_id_pro, "quantity": 1}],
        mode="subscription",
        success_url="http://localhost:3000/billing/success",
        cancel_url="http://localhost:3000/billing/cancel",
        metadata={"user_id": str(current_user.id)},
    )
    return CheckoutResponse(url=session.url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stripe 顧客ポータル（解約・カード変更）の URL を返す"""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe 未設定")
    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Stripe 顧客が未作成です")

    session = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
        return_url="http://localhost:3000/account",
    )
    return PortalResponse(url=session.url)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Stripe Webhook を受信してサブスクリプション状態を DB に反映する。

    処理するイベント:
    - customer.subscription.created / updated → plan = "pro"
    - customer.subscription.deleted           → plan = "free"
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Webhook 署名検証失敗")

    event_type = event["type"]
    subscription = event["data"]["object"]

    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        customer_id = subscription.get("customer")
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        if user:
            if event_type == "customer.subscription.deleted":
                user.plan = "free"
                user.stripe_subscription_id = None
                user.plan_expires_at = None
            else:
                status_str = subscription.get("status")
                # active / trialing → pro、それ以外 → free
                user.plan = "pro" if status_str in ("active", "trialing") else "free"
                user.stripe_subscription_id = subscription.get("id")
                period_end = subscription.get("current_period_end")
                if period_end:
                    user.plan_expires_at = datetime.fromtimestamp(period_end, tz=timezone.utc)
            await db.commit()

    return {"received": True}
