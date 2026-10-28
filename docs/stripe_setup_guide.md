# Stripe 課金フロー セットアップガイド

## 概要

このプロジェクトでは Stripe を使った月額サブスクリプション（¥2,980/月）を実装しています。
以下の手順でローカルテストから本番まで設定できます。

---

## Step 1: Stripe アカウントとキー取得

1. https://dashboard.stripe.com にログイン
2. 右上のトグルで **テストモード** になっていることを確認
3. 「開発者」→「API キー」から以下を取得:
   - `sk_test_...` → `STRIPE_SECRET_KEY`

---

## Step 2: Product + Price を自動作成

```bash
# プロジェクトルートで実行
STRIPE_SECRET_KEY=sk_test_xxxx python scripts/stripe_setup.py
```

または `.env` に `STRIPE_SECRET_KEY` を書いておけば:

```bash
python scripts/stripe_setup.py
```

実行すると:
- Stripe に **Stock Intelligence Pro**（¥2,980/月）を作成
- `.env` の `STRIPE_PRICE_ID_PRO` を自動更新

---

## Step 3: Stripe CLI で Webhook をローカルに転送

Stripe CLI をインストール（未インストールの場合）:

```bash
# macOS
brew install stripe/stripe-cli/stripe

# Linux
wget -O /tmp/stripe.tar.gz https://github.com/stripe/stripe-cli/releases/latest/download/stripe_linux_x86_64.tar.gz
tar -xvf /tmp/stripe.tar.gz -C /usr/local/bin
```

ログインして転送開始:

```bash
stripe login
stripe listen --forward-to localhost:8000/api/billing/webhook
```

出力される `whsec_...` を `.env` に設定:

```env
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxx
```

---

## Step 4: バックエンド再起動

```bash
docker compose up -d --build backend
```

---

## Step 5: 動作テスト

```bash
python scripts/stripe_test_checkout.py
```

出力された URL をブラウザで開き、テストカードで支払い:

| 項目 | 値 |
|------|-----|
| カード番号 | `4242 4242 4242 4242` |
| 有効期限 | `12/28`（任意の将来日付）|
| CVC | `123` |

支払い完了後、`stripe listen` ターミナルに webhook 受信ログが表示され、
DB の `users.plan` が `"pro"` になります。

---

## 本番移行チェックリスト

- [ ] Stripe ダッシュボードで **本番モード** に切り替え
- [ ] `sk_live_...` キーを `.env` に設定
- [ ] `stripe_setup.py` を本番キーで再実行（Price を本番で作成）
- [ ] 本番サーバーの Webhook エンドポイントを Stripe ダッシュボードに登録
  - エンドポイント URL: `https://your-domain.com/api/billing/webhook`
  - 購読イベント: `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`
- [ ] 本番 `STRIPE_WEBHOOK_SECRET`（`whsec_live_...`）を設定

---

## トラブルシューティング

### Checkout URL が返ってこない
- `.env` の `STRIPE_SECRET_KEY` と `STRIPE_PRICE_ID_PRO` を確認
- `docker compose logs backend` でエラーを確認

### Webhook が届かない
- `stripe listen` が起動しているか確認
- `STRIPE_WEBHOOK_SECRET` が `whsec_...` から始まるか確認
- ポート 8000 が開いているか確認

### plan が pro に変わらない
- `stripe listen` のログに `200 OK` が表示されているか確認
- `docker compose logs backend` で webhook エラーを確認
