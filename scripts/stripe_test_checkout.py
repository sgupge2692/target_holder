#!/usr/bin/env python3
"""
Stripe 課金フロー 簡易テストスクリプト
========================================
ローカルの FastAPI バックエンドに対して:
  1. ユーザー登録 or ログインして JWT を取得
  2. /api/billing/checkout を叩いて Checkout URL を取得
  3. URL を表示（ブラウザで開いてテストカードで支払い）

前提:
  - docker compose up -d で backend が起動済み
  - stripe listen --forward-to localhost:8000/api/billing/webhook を別ターミナルで実行中

使い方:
  python scripts/stripe_test_checkout.py
  python scripts/stripe_test_checkout.py --email test@example.com --password testpass
"""

import argparse
import json
import urllib.request
import urllib.error
import sys

BASE_URL = "http://localhost:8000"


def post(path: str, data: dict, token: str = "") -> dict:
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[ERROR] {e.code} {e.reason}: {body}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default="stripe_test@example.com")
    parser.add_argument("--password", default="TestPass123!")
    args = parser.parse_args()

    email = args.email
    password = args.password

    # ── 1. 登録を試みる（既存なら失敗するが無視） ─────────────────
    print(f"[1/3] ユーザー登録: {email}")
    try:
        post("/api/auth/register", {"email": email, "password": password})
        print("      → 登録成功")
    except SystemExit:
        print("      → 既存ユーザー（ログインに進みます）")

    # ── 2. ログインして JWT 取得 ─────────────────────────────────
    print(f"[2/3] ログイン...")
    # FastAPI の OAuth2 フォームエンドポイントに対応
    url = f"{BASE_URL}/api/auth/login"
    import urllib.parse
    form_data = urllib.parse.urlencode({"username": email, "password": password}).encode()
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(url, data=form_data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            login_resp = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        # JSON ボディでのログインにフォールバック
        try:
            login_resp = post("/api/auth/login", {"email": email, "password": password})
        except SystemExit:
            print("[ERROR] ログイン失敗。バックエンドが起動しているか確認してください。")
            sys.exit(1)

    token = login_resp.get("access_token") or login_resp.get("token", "")
    if not token:
        print(f"[ERROR] トークン取得失敗: {login_resp}")
        sys.exit(1)
    print(f"      → JWT 取得: {token[:20]}...")

    # ── 3. Checkout セッション作成 ───────────────────────────────
    print(f"[3/3] Checkout セッション作成...")
    checkout = post("/api/billing/checkout", {}, token=token)
    url = checkout.get("url", "")
    if not url:
        print(f"[ERROR] URL が返ってきませんでした: {checkout}")
        sys.exit(1)

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Checkout URL を取得しました ✅
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  {url}

  ↑ ブラウザで開いて以下のテストカードで支払ってください:

  カード番号 : 4242 4242 4242 4242
  有効期限   : 任意の将来日付 (例: 12/28)
  CVC       : 任意3桁 (例: 123)
  郵便番号   : 任意 (例: 100-0001)

  支払い完了後、webhook が受信されて DB の plan が "pro" になります。
  確認: docker compose exec backend python -c "
    import asyncio
    from app.database import get_db
    from app.models import User
    from sqlalchemy import select
    async def check():
        async for db in get_db():
            r = await db.execute(select(User).where(User.email=='{email}'))
            u = r.scalar_one_or_none()
            print('plan:', u.plan if u else 'user not found')
    asyncio.run(check())
  "
""")


if __name__ == "__main__":
    main()
