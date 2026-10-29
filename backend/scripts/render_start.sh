#!/bin/bash
# Render デプロイ時に自動実行: マイグレーション → サーバー起動

set -e

echo "=== Alembic マイグレーション実行 ==="
alembic upgrade head

echo "=== サーバー起動 ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
