"""
課金エンドポイント (Stripe)
- GET  /api/billing/plans     : 利用可能な課金間隔と金額（月払い/年払い）
- POST /api/billing/checkout  : Stripe Checkout セッション作成（interval: month | year）
- POST /api/billing/portal    : 顧客ポータル URL 取得
- POST /api/billing/webhook   : Stripe Webhook 受信
"""
import time
import stripe
from datetime import datetime, timezone
from typing import Literal, Optional

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

class CheckoutRequest(BaseModel):
    interval: Literal["month", "year"] = "month"


class CheckoutResponse(BaseModel):
    url: str


class PlansResponse(BaseModel):
    yearly_available: bool
    monthly_amount: Optional[int] = None   # 円（Stripe の Price から取得。取得できなければ None）
    yearly_amount: Optional[int] = None


class PortalResponse(BaseModel):
    url: str


# ── ヘルパー ──────────────────────────────────────────────────

_PRICE_CACHE: dict[str, tuple[float, Optional[int]]] = {}
_PRICE_CACHE_TTL = 600  # 秒


def _price_id_for(interval: str) -> str:
    return settings.stripe_price_id_pro_yearly if interval == "year" else settings.stripe_price_id_pro


def _price_amount(price_id: str) -> Optional[int]:
    """Stripe の Price から金額（JPY は最小単位=円）を取得。表示と実際の請求額がずれないようにする。"""
    if not price_id or not settings.stripe_secret_key:
        return None
    now = time.monotonic()
    cached = _PRICE_CACHE.get(price_id)
    if cached and now - cached[0] < _PRICE_CACHE_TTL:
        return cached[1]
    try:
        amount = stripe.Price.retrieve(price_id).unit_amount
    except Exception:
        amount = None
    _PRICE_CACHE[price_id] = (now, amount)
    return amount


async def _get_or_create_customer(user: User, db: AsyncSession) -> str:
    """Stripe 顧客IDを取得 or 新規作成してDBに保存"""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = stripe.Customer.create(email=user.email, metadata={"user_id": str(user.id)})
    user.stripe_customer_id = customer.id
    await db.commit()
    return customer.id


# ── エンドポイント ────────────────────────────────────────────

@router.get("/plans", response_model=PlansResponse)
async def get_plans():
    """月払い・年払いの利用可否と金額（認証不要。料金ページ用）"""
    yearly_id = settings.stripe_price_id_pro_yearly
    return PlansResponse(
        yearly_available=bool(yearly_id),
        monthly_amount=_price_amount(settings.stripe_price_id_pro),
        yearly_amount=_price_amount(yearly_id),
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    body: Optional[CheckoutRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stripe Checkout セッションを作成して支払いページ URL を返す（body 省略時は月払い）"""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe 未設定")

    interval = body.interval if body else "month"
    if interval == "year" and not settings.stripe_price_id_pro_yearly:
        raise HTTPException(status_code=400, detail="年払いプランは現在ご利用いただけません")
    if current_user.plan == "pro":
        # 二重にサブスクリプションを作らない（プラン変更・解約はポータルから）
        raise HTTPException(status_code=400, detail="すでにProプランです。プランの変更はカスタマーポータルから行えます")

    customer_id = await _get_or_create_customer(current_user, db)

    base = settings.frontend_url.rstrip("/")
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": _price_id_for(interval), "quantity": 1}],
        mode="subscription",
        success_url=f"{base}/billing/success",
        cancel_url=f"{base}/billing",
        metadata={"user_id": str(current_user.id), "interval": interval},
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

    base = settings.frontend_url.rstrip("/")
    session = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
        return_url=f"{base}/account",
    )
    return PortalResponse(url=session.url)


@router.get("/subscription")
async def get_subscription(
    current_user: User = Depends(get_current_user),
):
    """現在のサブスクリプション情報を返す"""
    return {
        "plan": current_user.plan,
        "plan_expires_at": current_user.plan_expires_at.isoformat() if current_user.plan_expires_at else None,
        "stripe_subscription_id": current_user.stripe_subscription_id,
    }


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
