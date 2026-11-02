"""
通知設定エンドポイント: GET/PATCH /api/notifications/settings
配信停止エンドポイント: GET /api/notifications/unsubscribe (認証不要・トークンで認証)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.notifications import make_unsubscribe_token

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationSettings(BaseModel):
    email_signal_alert: bool
    email_unsubscribed: bool


class UpdateNotificationSettings(BaseModel):
    email_signal_alert: bool | None = None
    email_unsubscribed: bool | None = None


@router.get("/settings", response_model=NotificationSettings)
async def get_settings(
    current_user: User = Depends(get_current_user),
):
    return NotificationSettings(
        email_signal_alert=current_user.email_signal_alert,
        email_unsubscribed=current_user.email_unsubscribed,
    )


@router.patch("/settings", response_model=NotificationSettings)
async def update_settings(
    body: UpdateNotificationSettings,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Pro ユーザーのみ email_signal_alert を有効にできる
    if body.email_signal_alert and current_user.plan != "pro":
        raise HTTPException(
            status_code=403,
            detail="メールアラートはProプラン限定機能です",
        )

    if body.email_signal_alert is not None:
        current_user.email_signal_alert = body.email_signal_alert
    if body.email_unsubscribed is not None:
        current_user.email_unsubscribed = body.email_unsubscribed

    await db.commit()
    await db.refresh(current_user)

    return NotificationSettings(
        email_signal_alert=current_user.email_signal_alert,
        email_unsubscribed=current_user.email_unsubscribed,
    )


@router.get("/unsubscribe", response_class=HTMLResponse, include_in_schema=False)
async def one_click_unsubscribe(
    uid: int = Query(..., description="ユーザーID"),
    token: str = Query(..., description="HMACトークン"),
    db: AsyncSession = Depends(get_db),
):
    """
    ワンクリック配信停止（認証不要）
    メール本文のリンクから直接呼び出される。
    """
    result = await db.execute(select(User).where(User.id == uid))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

    # HMAC トークン検証
    expected = make_unsubscribe_token(user.id, user.email)
    if token != expected:
        raise HTTPException(status_code=403, detail="無効なトークンです")

    if not user.email_unsubscribed:
        user.email_unsubscribed = True
        user.email_signal_alert = False
        await db.commit()

    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>配信停止完了</title>
<style>body{font-family:-apple-system,sans-serif;max-width:480px;margin:80px auto;text-align:center;color:#374151;}
h1{color:#16a34a;}a{color:#6366f1;}</style></head>
<body>
<h1>✓ 配信停止が完了しました</h1>
<p>今後、メールシグナルアラートは送信されません。</p>
<p style="font-size:13px;color:#9ca3af;">
  再度有効にするにはダッシュボードの通知設定から変更できます。
</p>
<a href="/">ダッシュボードへ戻る</a>
</body></html>""", status_code=200)
