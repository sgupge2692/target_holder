# VPS デプロイ手順

## 前提条件

| 項目 | 推奨スペック |
|------|------------|
| OS | Ubuntu 22.04 LTS |
| CPU | 2 vCPU 以上 |
| RAM | 4 GB 以上（ML モデル込み）|
| ディスク | 40 GB 以上 |
| ドメイン | 取得済み + A レコードを VPS IP に向けること |

---

## 1. VPS の初期設定

```bash
# SSH ログイン後
sudo apt-get update && sudo apt-get upgrade -y

# Docker インストール
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # 一度ログアウトして再ログイン

# Docker Compose v2 確認
docker compose version
```

---

## 2. リポジトリのクローン

```bash
git clone https://github.com/YOUR_ORG/stock-intelligence.git /opt/stock-intelligence
cd /opt/stock-intelligence
```

---

## 3. 環境変数の設定

```bash
cp .env.example .env
nano .env   # 以下の項目を必ず埋める
```

**必須項目チェックリスト:**

- [ ] `DB_USER` / `DB_PASSWORD` / `DB_NAME`
- [ ] `JWT_SECRET` (32文字以上のランダム文字列)
- [ ] `JQUANTS_MAIL_ADDRESS` / `JQUANTS_PASSWORD`
- [ ] `OPENAI_API_KEY`
- [ ] `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / `STRIPE_PRICE_ID_PRO`
- [ ] `CORS_ORIGINS=https://your-domain.com`
- [ ] `NEXT_PUBLIC_SITE_URL=https://your-domain.com`
- [ ] `EMAIL_PROVIDER` + SMTP / SendGrid 設定
- [ ] `ADMIN_EMAILS`
- [ ] `SENTRY_DSN` / `NEXT_PUBLIC_SENTRY_DSN` (任意)
- [ ] `TWITTER_API_KEY` など (任意)

```bash
# JWT_SECRET の生成例
openssl rand -hex 32
```

---

## 4. SSL 証明書の取得 (Let's Encrypt)

```bash
# Nginx コンテナが起動する前に証明書を取得
docker run --rm \
  -v $(pwd)/nginx/ssl:/etc/letsencrypt \
  -v $(pwd)/nginx/certbot-www:/var/www/certbot \
  -p 80:80 \
  certbot/certbot certonly --standalone \
  -d your-domain.com -d www.your-domain.com \
  --email admin@your-domain.com \
  --agree-tos --non-interactive

# nginx.conf の server_name を自分のドメインに変更
nano nginx/nginx.conf   # stock-intelligence.app → your-domain.com
```

---

## 5. 初回起動

```bash
# ビルド & 起動
make prod-build

# DB マイグレーション
make migrate

# ログを確認
make prod-logs
```

---

## 6. Stripe Webhook の設定

Stripe ダッシュボード → Developers → Webhooks → Add endpoint

- **Endpoint URL**: `https://your-domain.com/api/billing/webhook`
- **Events**: `checkout.session.completed`, `customer.subscription.deleted`

取得した **Signing secret** を `.env` の `STRIPE_WEBHOOK_SECRET` に設定し、バックエンドを再起動:

```bash
make prod-restart
```

---

## 7. GitHub Actions の設定 (CI/CD)

リポジトリの **Settings → Secrets and variables → Actions** で以下を追加:

| Secret 名 | 値 |
|-----------|---|
| `VPS_HOST` | VPS の IP アドレス |
| `VPS_USER` | SSH ユーザー名 (例: `ubuntu`) |
| `VPS_SSH_KEY` | SSH 秘密鍵の内容 (`cat ~/.ssh/id_rsa`) |
| `VPS_PORT` | SSH ポート (デフォルト: `22`) |

これで `main` ブランチへの push 時に自動デプロイされます。

---

## 8. 動作確認

```bash
# ヘルスチェック
curl https://your-domain.com/health   # {"status":"ok"}

# API テスト
curl https://your-domain.com/api/signals/accuracy
```

---

## 9. cron スクリプト動作確認

```bash
# cron コンテナのログ確認
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs cron

# 手動でシグナル送信スクリプトをテスト
docker compose exec cron python /scripts/send_daily_signals.py
```

---

## 10. よくあるトラブル

### DB 接続エラー
```bash
# DB コンテナが起動しているか確認
docker compose ps db
# healthcheck の状態確認
docker inspect stock_db | grep Health -A 20
```

### 証明書エラー (nginx 502)
```bash
# 証明書ファイルの存在確認
ls nginx/ssl/live/your-domain.com/
# 証明書の有効期限確認
docker compose exec nginx nginx -t
```

### メモリ不足
```bash
# コンテナのメモリ使用量確認
docker stats --no-stream
# swap を有効化 (4 GB)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 11. 更新デプロイ

```bash
git pull
make prod-build
make migrate
```

または GitHub の `main` ブランチに push するだけで自動デプロイされます。
