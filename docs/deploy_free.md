# 無料デプロイ手順

Vercel + Render + Supabase + Upstash の完全無料構成

---

## 必要なアカウント（すべて無料）

| サービス | 用途 | URL |
|---------|------|-----|
| Vercel | フロントエンド | https://vercel.com |
| Render | バックエンドAPI | https://render.com |
| Supabase | PostgreSQL DB | https://supabase.com |
| Upstash | Redis | https://upstash.com |

---

## 手順

### 1. Supabase でデータベース作成

1. https://supabase.com → New Project
2. Database Password をメモ
3. Settings → Database → Connection string (URI) をコピー
   - `postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres`
4. **asyncpg用に変換**: `postgresql+asyncpg://...` に変更

### 2. Upstash で Redis 作成

1. https://upstash.com → Create Database
2. Region: `ap-northeast-1`（東京）
3. REST URL と Token をメモ
4. 「Redis URL」をコピー: `rediss://default:[TOKEN]@[HOST]:6379`

### 3. Render でバックエンドをデプロイ

1. https://render.com → New → Web Service
2. GitHub リポジトリを選択
3. 設定:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `bash scripts/render_start.sh`
   - **Plan**: Free
4. Environment Variables を設定:
   ```
   DATABASE_URL=postgresql+asyncpg://postgres:[PW]@db.[REF].supabase.co:5432/postgres
   REDIS_URL=rediss://default:[TOKEN]@[HOST]:6379
   JWT_SECRET=[ランダムな文字列32文字以上]
   ADMIN_EMAILS=自分のメールアドレス
   FRONTEND_URL=https://your-app.vercel.app（後で更新）
   ```
5. デプロイ完了後、URL をメモ: `https://stock-intelligence-api.onrender.com`

### 4. Vercel でフロントエンドをデプロイ

1. https://vercel.com → Add New Project
2. GitHub リポジトリを選択
3. **Root Directory**: `frontend`
4. Environment Variables:
   ```
   NEXT_PUBLIC_API_URL=https://stock-intelligence-api.onrender.com
   NEXT_PUBLIC_SITE_URL=https://your-app.vercel.app
   ```
5. デプロイ → URLをメモ

### 5. RenderのFRONTEND_URLを更新

Render ダッシュボード → Environment → `FRONTEND_URL` を Vercel のURL に更新

### 6. Vercel の vercel.json を更新

`frontend/vercel.json` の `destination` を Render の URL に変更:
```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://stock-intelligence-api.onrender.com/api/:path*"
    }
  ]
}
```
→ git push すれば自動で再デプロイ

### 7. MLパイプライン有効化（GitHub Actions）

Secrets と Variables を設定:

**Settings → Secrets → Actions:**
```
DATABASE_URL=（Supabase の接続文字列）
OPENAI_API_KEY=（任意）
JQUANTS_MAIL_ADDRESS=（任意）
JQUANTS_PASSWORD=（任意）
```

**Settings → Variables → Actions:**
```
ML_ENABLED=true
```

→ 毎営業日 6:30 JST に自動予測が走る

---

## 無料枠の制限

| サービス | 制限 |
|---------|------|
| Render Free | 15分アクセスなしでスリープ（初回アクセスが遅い） |
| Supabase Free | DB 500MB、一時停止なし |
| Upstash Free | 10,000コマンド/日 |
| Vercel Free | 100GB帯域/月、無制限デプロイ |
| GitHub Actions | 2,000分/月（privateリポジトリ） |

## Render のスリープ対策

無料プランは15分アクセスがないとスリープします。
対策として UptimeRobot（無料）で5分おきにヘルスチェックを設定:
- https://uptimerobot.com
- Monitor Type: HTTP(s)
- URL: `https://stock-intelligence-api.onrender.com/api/health`
- Monitoring Interval: 5 minutes
