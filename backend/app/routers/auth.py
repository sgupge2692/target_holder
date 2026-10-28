"""
認証エンドポイント: register / login / me / password-reset
"""
import os
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import hash_password, verify_password, create_access_token, get_current_user
from app.database import get_db
from app.limiter import limiter
from app.models import User
from app.notifications import send_email, render_welcome_email

router = APIRouter(prefix="/api/auth", tags=["auth"])

SITE_URL = os.getenv("NEXT_PUBLIC_SITE_URL", "https://stock-intelligence.app")
RESET_TOKEN_EXPIRE_HOURS = 1


# ── スキーマ ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    plan: str

    model_config = {"from_attributes": True}


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


# ── エンドポイント ────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="このメールアドレスは既に登録されています")

    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # ウェルカムメールをバックグラウンドで送信
    username = body.email.split("@")[0]
    html = render_welcome_email(username=username, site_url=SITE_URL)
    background_tasks.add_task(
        send_email,
        to=body.email,
        subject="【Stock Intelligence】ご登録ありがとうございます",
        html=html,
    )

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="メールアドレスまたはパスワードが違います",
        )

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/password-reset/request", status_code=202)
@limiter.limit("3/minute")
async def request_password_reset(
    request: Request,
    body: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """パスワードリセットメールを送信（ユーザーが存在しなくても 202 を返す）"""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user:
        token = secrets.token_urlsafe(48)
        user.reset_token = token
        user.reset_token_expires_at = datetime.utcnow() + timedelta(hours=RESET_TOKEN_EXPIRE_HOURS)
        await db.commit()

        reset_url = f"{SITE_URL}/auth/reset-password?token={token}"
        html = _render_reset_email(reset_url)
        background_tasks.add_task(
            send_email,
            to=body.email,
            subject="【Stock Intelligence】パスワードリセット",
            html=html,
        )

    # セキュリティ: ユーザーの存在有無を漏らさない
    return {"message": "該当するメールアドレスにリセットリンクを送信しました（登録済みの場合）"}


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    body: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """トークンを検証してパスワードを更新"""
    result = await db.execute(
        select(User).where(User.reset_token == body.token)
    )
    user = result.scalar_one_or_none()

    if not user or not user.reset_token_expires_at:
        raise HTTPException(status_code=400, detail="無効なリセットトークンです")

    if datetime.utcnow() > user.reset_token_expires_at:
        raise HTTPException(status_code=400, detail="リセットトークンの有効期限が切れています")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=422, detail="パスワードは8文字以上で設定してください")

    user.hashed_password = hash_password(body.new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    await db.commit()

    return {"message": "パスワードを変更しました"}


# ── メールテンプレート ─────────────────────────────────────────

def _render_reset_email(reset_url: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>パスワードリセット</title></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,sans-serif;">
<div style="max-width:600px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">
  <div style="background:#0f172a;padding:28px 32px;">
    <h1 style="color:#fff;margin:0;font-size:20px;">📈 <span style="color:#22c55e;">Stock Intelligence</span></h1>
  </div>
  <div style="padding:32px;">
    <h2 style="margin-top:0;color:#0f172a;">パスワードリセット</h2>
    <p style="color:#475569;">以下のボタンをクリックして新しいパスワードを設定してください。</p>
    <p style="color:#475569;">このリンクは<strong>{RESET_TOKEN_EXPIRE_HOURS}時間</strong>有効です。</p>
    <a href="{reset_url}"
       style="display:inline-block;background:#22c55e;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:700;font-size:15px;margin-top:8px;">
      パスワードをリセット →
    </a>
    <p style="margin-top:24px;font-size:12px;color:#94a3b8;">
      このメールに心当たりがない場合は無視してください。
    </p>
  </div>
</div>
</body>
</html>"""
