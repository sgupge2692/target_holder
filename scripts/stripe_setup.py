#!/usr/bin/env python3
"""
Stripe セットアップスクリプト
================================
実行すると以下を自動で行います:
  1. Stripe に Product (Stock Intelligence Pro) を作成
  2. 月額 ¥2,980 の Price を作成
  3. プロジェクトルートの .env を更新 (STRIPE_PRICE_ID_PRO を書き込み)
  4. Stripe CLI の webhook forward コマンドを表示

使い方:
  STRIPE_SECRET_KEY=sk_test_xxxx python scripts/stripe_setup.py

  または .env に STRIPE_SECRET_KEY が書かれていれば:
  python scripts/stripe_setup.py
"""

import os
import re
import sys
from pathlib import Path

# ── stripe インポート ──────────────────────────────────────────
try:
    import stripe
except ImportError:
    print("[ERROR] stripe が未インストールです。")
    print("       pip install stripe  を実行してください。")
    sys.exit(1)

# ── .env ロード（dotenv がなくても手動パース）────────────────────
ROOT = Path(__file__).parent.parent
ENV_FILE = ROOT / ".env"


def load_dotenv_simple(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


dotenv = load_dotenv_simple(ENV_FILE)

# ── Stripe キー取得 ───────────────────────────────────────────
stripe_secret = os.environ.get("STRIPE_SECRET_KEY") or dotenv.get("STRIPE_SECRET_KEY", "")

if not stripe_secret:
    print("[ERROR] STRIPE_SECRET_KEY が見つかりません。")
    print("       環境変数か .env に設定してください。")
    sys.exit(1)

if not stripe_secret.startswith("sk_"):
    print(f"[ERROR] STRIPE_SECRET_KEY の形式が不正です: {stripe_secret[:10]}...")
    sys.exit(1)

stripe.api_key = stripe_secret
is_test = stripe_secret.startswith("sk_test_")
mode_label = "TEST" if is_test else "LIVE"
print(f"[INFO] Stripe {mode_label} モードで接続します")

# ── 既存 Product の確認 ───────────────────────────────────────
PRODUCT_NAME = "Stock Intelligence Pro"
PRICE_AMOUNT = 2980          # 円
PRICE_CURRENCY = "jpy"
PRICE_INTERVAL = "month"

print(f"\n[1/4] Product を検索中: {PRODUCT_NAME}")
existing_product = None
for product in stripe.Product.list(limit=100).auto_paging_iter():
    if product.name == PRODUCT_NAME and product.active:
        existing_product = product
        print(f"      → 既存 Product を再利用: {product.id}")
        break

if not existing_product:
    existing_product = stripe.Product.create(
        name=PRODUCT_NAME,
        description="株価予測シグナル・AI説明・銘柄詳細への無制限アクセス",
        metadata={"tier": "pro"},
    )
    print(f"      → 新規作成: {existing_product.id}")

# ── 既存 Price の確認 ─────────────────────────────────────────
print(f"\n[2/4] Price を検索中: ¥{PRICE_AMOUNT:,}/{PRICE_INTERVAL}")
existing_price = None
for price in stripe.Price.list(product=existing_product.id, limit=100).auto_paging_iter():
    if (
        price.active
        and price.currency == PRICE_CURRENCY
        and price.unit_amount == PRICE_AMOUNT
        and price.recurring
        and price.recurring.interval == PRICE_INTERVAL
    ):
        existing_price = price
        print(f"      → 既存 Price を再利用: {price.id}")
        break

if not existing_price:
    existing_price = stripe.Price.create(
        product=existing_product.id,
        unit_amount=PRICE_AMOUNT,
        currency=PRICE_CURRENCY,
        recurring={"interval": PRICE_INTERVAL},
        metadata={"plan": "pro"},
    )
    print(f"      → 新規作成: {existing_price.id}")

price_id = existing_price.id

# ── .env を更新 ───────────────────────────────────────────────
print(f"\n[3/4] .env を更新中: {ENV_FILE}")

if ENV_FILE.exists():
    content = ENV_FILE.read_text()
    if "STRIPE_PRICE_ID_PRO" in content:
        content = re.sub(
            r"^STRIPE_PRICE_ID_PRO=.*$",
            f"STRIPE_PRICE_ID_PRO={price_id}",
            content,
            flags=re.MULTILINE,
        )
        print(f"      → STRIPE_PRICE_ID_PRO を上書き")
    else:
        content += f"\nSTRIPE_PRICE_ID_PRO={price_id}\n"
        print(f"      → STRIPE_PRICE_ID_PRO を追記")
    ENV_FILE.write_text(content)
else:
    # .env が存在しない場合は .env.example をコピーして作成
    example = ROOT / ".env.example"
    base = example.read_text() if example.exists() else ""
    base += f"\nSTRIPE_PRICE_ID_PRO={price_id}\n"
    ENV_FILE.write_text(base)
    print(f"      → .env を新規作成")

# ── 完了メッセージ ────────────────────────────────────────────
print(f"\n[4/4] セットアップ完了 ✅")
print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Product ID  : {existing_product.id}
  Price ID    : {price_id}
  金額        : ¥{PRICE_AMOUNT:,} / {PRICE_INTERVAL}
  モード      : {mode_label}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

次のステップ:

  1. .env に STRIPE_SECRET_KEY と STRIPE_WEBHOOK_SECRET を確認
       STRIPE_SECRET_KEY={stripe_secret[:12]}...
       STRIPE_PRICE_ID_PRO={price_id}  ← 書き込み済み

  2. Webhook をローカルに転送（Stripe CLI が必要）:
       stripe listen --forward-to localhost:8000/api/billing/webhook

     上記コマンドを実行すると表示される
     whsec_... を .env の STRIPE_WEBHOOK_SECRET に設定してください。

  3. Docker を再起動:
       docker compose up -d --build backend

  4. 動作テスト:
       - ブラウザで http://localhost:3000 を開く
       - ユーザー登録 → 課金ページ → テストカード 4242 4242 4242 4242
       - plan が "pro" になるか確認
""")
