# KABUMI — 日本株 AI シグナル

LightGBM × XGBoost アンサンブルによる翌日騰落予測 + 資産管理 Web アプリ。

## スタック

| レイヤー | 技術 |
|---|---|
| フロントエンド | Next.js 14 (App Router) + Tailwind CSS |
| バックエンド | FastAPI + SQLAlchemy (async) + Alembic |
| ML | LightGBM / XGBoost / scikit-learn |
| DB | PostgreSQL |
| キャッシュ | Redis |
| インフラ | Docker Compose |
| データ | J-Quants API（無料ティア: 2年分の日足）|

---

## ローカルで動かす

### 1. 必要なもの

- **Docker Desktop**（または Docker Engine + Compose plugin）
- **J-Quants アカウント**（無料）→ https://jpx-jquants.com
  - 登録後にメールアドレス・パスワードを控えておく
- Git

> Stripe・OpenAI・Sentry は任意。なくても起動・予測まで動作する。

---

### 2. クローン & 環境変数の設定

```bash
git clone https://github.com/sgupge2692/target_holder.git
cd target_holder

cp .env.example .env
```

`.env` を開いて **最低限これだけ** 埋める：

```dotenv
# J-Quants（必須）
JQUANTS_MAIL_ADDRESS=your@email.com
JQUANTS_PASSWORD=your-password

# JWT（必須 — 何でも OK、32文字以上推奨）
JWT_SECRET=change-me-to-something-random

# 自分のメールアドレス → 自動で永久 Pro 付与
OWNER_EMAILS=your@email.com
ADMIN_EMAILS=your@email.com
```

---

### 3. 起動

```bash
docker compose up --build
```

初回は数分かかります。起動したら：

| URL | 内容 |
|---|---|
| http://localhost:3000 | フロントエンド |
| http://localhost:8000/docs | FastAPI Swagger UI |
| http://localhost:8000/health | ヘルスチェック |

---

### 4. ML パイプラインを回す

起動後、別ターミナルで順番に実行：

```bash
# ① 株価データ取得（J-Quants API → DB、初回は数分）
docker compose run --rm ml python pipeline/fetch_data.py

# ② 特徴量エンジニアリング
docker compose run --rm ml python pipeline/feature_engineering.py

# ③ 学習（LightGBM + XGBoost アンサンブル）
docker compose run --rm ml python pipeline/train.py --mode ensemble

# ④ 予測実行 → DB に保存
docker compose run --rm ml python pipeline/predict.py
```

http://localhost:3000 を開くとシグナルが表示されます。

---

## ディレクトリ構成

```
target_holder/
├── backend/              FastAPI バックエンド
│   ├── app/
│   │   ├── routers/      エンドポイント (auth / signals / assets / ...)
│   │   ├── models.py     SQLAlchemy モデル
│   │   └── main.py       FastAPI アプリ
│   └── alembic/          DB マイグレーション
│
├── frontend/             Next.js フロントエンド
│   └── src/
│       ├── app/          ページ (page.tsx / assets / backtest / ...)
│       ├── components/   共通コンポーネント
│       └── lib/          API クライアント
│
├── ml/                   機械学習パイプライン
│   └── pipeline/
│       ├── fetch_data.py          J-Quants から日足取得
│       ├── feature_engineering.py テクニカル指標計算
│       ├── train.py               LightGBM / XGBoost 学習
│       └── predict.py             翌日シグナル生成
│
├── nginx/                リバースプロキシ設定
├── .env.example          環境変数テンプレート
├── docker-compose.yml    本番向け Compose
└── LEARN.md              学習ロードマップ（ML / Web / MLOps）
```

---

## 主な機能

- **シグナルフィード** — 毎日更新。UP / DOWN シグナルを確度付きで表示
- **バックテスト** — 過去シグナルの的中率・平均リターンを確認
- **ウォッチリスト** — 気になる銘柄を登録してまとめて追跡
- **資産管理** — 現金・株・不動産・負債を登録して純資産推移を可視化
- **Pro プラン** — スイング / 長期保有 / 信用売りモード + CSV エクスポート（Stripe 連携）

---

## よくある質問

**Q: J-Quants の無料ティアで十分ですか？**
A: はい。2年分の日足 + 銘柄情報が使えるので十分です。

**Q: 予測はどのくらい当たりますか？**
A: バックテスト上で UP シグナル約 60〜65% の的中率（市場環境に依存）。投資判断の参考として使ってください。

**Q: OpenAI API キーがなくても動きますか？**
A: 動きます。キーがない場合はシグナル解説文が非表示になるだけです。

**Q: 本番公開したい場合は？**
A: `docker-compose.prod.yml` に VPS 向けの設定があります。ドメイン取得 → Nginx SSL 設定 → Stripe 本番 Webhook 登録 の順で進めてください。

---

## ライセンス

MIT
