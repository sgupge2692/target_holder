# Stock Intelligence

日本株特化のAI株価予測・企業要約サービス

## セットアップ

### 必要なもの
- Docker / Docker Compose
- J-Quants APIキー（https://jpx-jquants.com）
- OpenAI APIキー

### 手順

```bash
# 1. リポジトリをクローン
git clone https://github.com/yourrepo/stock-intelligence
cd stock-intelligence

# 2. 環境変数を設定
cp .env.example .env
# .envをエディタで開いてAPIキーを記入

# 3. 開発環境を起動
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# 4. 動作確認
curl http://localhost:8000/health
# → {"status": "ok"}
```

### 各サービスのURL
- フロントエンド: http://localhost:3000
- バックエンドAPI: http://localhost:8000
- API docs: http://localhost:8000/docs

## MLパイプラインの手動実行

```bash
# データ取得
docker compose exec ml python pipeline/fetch_data.py

# 特徴量計算
docker compose exec ml python pipeline/feature_engineering.py

# 学習（フル）
docker compose exec ml python pipeline/train.py --mode full

# 学習（逐次）
docker compose exec ml python pipeline/train.py --mode incremental

# 予測実行
docker compose exec ml python pipeline/predict.py
```

## CI/CD（自動実行）

GitHub ActionsのSelf-hosted runnerをローカルPCに設定することで、
毎日15:35の日次パイプラインと毎週土曜深夜のフル再学習が自動実行されます。

Self-hosted runnerの設定:
1. GitHubリポジトリの Settings → Actions → Runners
2. "New self-hosted runner" をクリック
3. 指示に従ってローカルPCにrunnerをインストール

## ディレクトリ構成

```
stock-intelligence/
├── backend/        FastAPI バックエンド
├── frontend/       Next.js フロントエンド
├── ml/             機械学習パイプライン
├── db/             DBスキーマ
├── nginx/          リバースプロキシ設定
└── .github/        CI/CD ワークフロー
```
