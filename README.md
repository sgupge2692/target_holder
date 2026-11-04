# KABUMI — 日本株 AI シグナル

LightGBM × XGBoost アンサンブルによる翌日騰落予測 + 資産管理 Web アプリ。

## 動作確認（デモ起動）

**API キー不要。** 3 コマンドで全機能を試せる。

```bash
# 1. クローン
git clone https://github.com/sgupge2692/target_holder.git
cd target_holder

# 2. 起動（初回は数分かかる）
cp .env.example .env
docker compose up --build -d

# 3. デモデータを投入
docker compose run --rm backend python scripts/seed_demo.py
```

ブラウザで **http://localhost:3000** を開き、以下でログイン：

| | |
|---|---|
| Email | `demo@kabumi.app` |
| Password | `demo1234` |
| プラン | Pro（全機能解放済み） |

> デモデータには過去 60 日分のシグナル・的中履歴がセットで入る。

---

## 確認できる機能

| ページ | 内容 |
|---|---|
| **シグナルフィード** | 上昇 / 下落シグナル一覧・確度バー・AI解説 |
| **バックテスト** | 的中率・平均リターンの時系列グラフ |
| **ウォッチリスト** | 銘柄の登録・価格追跡 |
| **資産管理** | 現金・株・負債を登録して純資産推移を可視化 |
| **アカウント** | プラン確認・メール通知設定 |

---

## 本番運用（本物のシグナルを動かす場合）

J-Quants の無料アカウントを取得すれば実際の株価データで動く。

### 1. J-Quants 登録

https://jpx-jquants.com で無料アカウントを作成。

### 2. `.env` に追記

```dotenv
JQUANTS_MAIL_ADDRESS=your@email.com
JQUANTS_PASSWORD=your-password
JWT_SECRET=（32文字以上のランダム文字列）
OWNER_EMAILS=your@email.com   # 自分のメール → 永久 Pro 付与
ADMIN_EMAILS=your@email.com
```

### 3. ML パイプラインを実行

```bash
# 株価データ取得
docker compose run --rm ml python pipeline/fetch_data.py

# 特徴量計算
docker compose run --rm ml python pipeline/feature_engineering.py

# 学習（LightGBM + XGBoost アンサンブル）
docker compose run --rm ml python pipeline/train.py --mode ensemble

# 予測実行 → DB に保存・画面に反映
docker compose run --rm ml python pipeline/predict.py
```

---

## スタック

| レイヤー | 技術 |
|---|---|
| フロントエンド | Next.js 14 (App Router) + Tailwind CSS |
| バックエンド | FastAPI + SQLAlchemy (async) + Alembic |
| ML | LightGBM / XGBoost / scikit-learn |
| DB | PostgreSQL + TimescaleDB |
| キャッシュ | Redis |
| インフラ | Docker Compose |
| 株価データ | J-Quants API（無料ティア: 2年分の日足）|

## ディレクトリ構成

```
target_holder/
├── backend/
│   ├── app/routers/        エンドポイント (auth / signals / assets / ...)
│   ├── app/models.py       SQLAlchemy モデル
│   └── scripts/seed_demo.py  ← デモデータ投入スクリプト
├── frontend/src/
│   ├── app/                ページ (signal / assets / backtest / ...)
│   └── components/         共通コンポーネント
├── ml/pipeline/
│   ├── fetch_data.py       J-Quants から日足取得
│   ├── feature_engineering.py  テクニカル指標計算
│   ├── train.py            LightGBM / XGBoost 学習
│   └── predict.py          翌日シグナル生成
├── db/init.sql             初期スキーマ
├── .env.example            環境変数テンプレート
└── LEARN.md                学習ロードマップ（ML / Web / MLOps）
```

## よくある質問

**Q: デモ起動で何が確認できますか？**
A: シグナル一覧・バックテスト・ウォッチリスト・資産管理・各種 UI がすべて確認できます。予測値はダミーデータです。

**Q: Stripe / OpenAI がないと動きませんか？**
A: 動きます。Stripe がない場合は課金フローが使えないだけで、Pro 機能は `OWNER_EMAILS` に自分のメールを設定すれば無条件で使えます。OpenAI がない場合はシグナルの解説文が非表示になります。

**Q: 本番公開したいです。**
A: `docker-compose.prod.yml` に VPS 向けの設定があります。ドメイン取得 → Nginx SSL → Stripe 本番 Webhook 登録の順で進めてください。

## ライセンス

MIT
