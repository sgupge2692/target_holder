"""
通知設定エンドポイント: GET/PATCH /api/notifications/settings
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import User

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
