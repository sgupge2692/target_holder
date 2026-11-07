# ── かぶみ (Kabumi) Makefile ─────────────────────────────────────────────
.PHONY: help dev prod-up prod-down prod-logs migrate test lint build domain-setup

help:  ## このヘルプを表示
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── 開発 ────────────────────────────────────────────────────────────────────
dev:  ## 開発環境を起動 (docker-compose.dev.yml)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

dev-build:  ## 開発環境をビルドしてから起動
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

dev-down:  ## 開発環境を停止
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

# ── 本番 ────────────────────────────────────────────────────────────────────
prod-up:  ## 本番環境を起動
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

prod-build:  ## 本番環境をビルドしてから起動
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

prod-down:  ## 本番環境を停止
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down

prod-logs:  ## 本番ログをフォロー
	docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

prod-restart:  ## バックエンドだけ再起動
	docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend

# ── DB マイグレーション ──────────────────────────────────────────────────────
migrate:  ## Alembic マイグレーションを実行（本番）
	docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \
	  alembic upgrade head

migrate-dev:  ## Alembic マイグレーションを実行（開発）
	docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend \
	  alembic upgrade head

migrate-status:  ## マイグレーションの現在状態を確認
	docker compose exec backend alembic current

# ── テスト ─────────────────────────────────────────────────────────────────
test:  ## バックエンド + ML の全テストを実行
	docker compose exec backend pytest --tb=short -q
	docker compose exec ml pytest --tb=short -q

test-backend:  ## バックエンドテストのみ
	docker compose exec backend pytest --tb=short -v

test-ml:  ## ML テストのみ
	docker compose exec ml pytest --tb=short -v

# ── Lint / 静的解析 ──────────────────────────────────────────────────────────
lint:  ## 全サービスの lint を実行
	docker compose exec backend ruff check app/
	docker compose exec ml ruff check pipeline/
	cd frontend && npx tsc --noEmit && npx next lint

# ── ビルド確認 ───────────────────────────────────────────────────────────────
build:  ## 全 Docker イメージをビルド（プッシュなし）
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# ── デプロイ補助 ─────────────────────────────────────────────────────────────
domain-setup:  ## ドメイン名を nginx.conf と .env に反映 (例: make domain-setup DOMAIN=example.com)
	@if [ -z "$(DOMAIN)" ]; then echo "❌  DOMAIN を指定してください: make domain-setup DOMAIN=example.com"; exit 1; fi
	bash scripts/setup-domain.sh $(DOMAIN)

ssl-init:  ## Let's Encrypt 証明書の初回取得 (nginx 起動前に実行 / 80番ポートを使用)
	@if [ -z "$(DOMAIN)" ] || [ -z "$(EMAIL)" ]; then echo "Usage: make ssl-init DOMAIN=example.com EMAIL=admin@example.com"; exit 1; fi
	docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm -p 80:80 \
	  --entrypoint certbot certbot certonly --standalone \
	  -d $(DOMAIN) -d www.$(DOMAIN) \
	  --email $(EMAIL) --agree-tos --non-interactive

shell-backend:  ## バックエンドコンテナのシェルに入る
	docker compose exec backend bash

shell-db:  ## DB の psql に入る
	docker compose exec db psql -U $$DB_USER -d $$DB_NAME

# ── クリーンアップ ──────────────────────────────────────────────────────────
clean:  ## 停止済みコンテナ・未使用イメージを削除
	docker system prune -f

clean-all:  ## ボリュームも含めて全削除（データが消えるので注意！）
	docker compose down -v
	docker system prune -af
