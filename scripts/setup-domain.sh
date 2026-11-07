#!/usr/bin/env bash
# =============================================================================
# setup-domain.sh — ドメイン名を nginx.conf と .env に反映するセットアップスクリプト
# 使い方: bash scripts/setup-domain.sh <ドメイン名>
# 例:     bash scripts/setup-domain.sh example.com
# =============================================================================

set -euo pipefail

DOMAIN="${1:-}"

if [[ -z "$DOMAIN" ]]; then
  echo "❌  ドメイン名を引数で指定してください"
  echo "    使い方: bash scripts/setup-domain.sh example.com"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🌐  ドメイン: $DOMAIN"
echo "📁  プロジェクトルート: $ROOT_DIR"
echo ""

# ── 1. nginx/nginx.conf をテンプレートから生成 ────────────────────────────
TEMPLATE="$ROOT_DIR/nginx/nginx.conf.template"
CONF="$ROOT_DIR/nginx/nginx.conf"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "❌  テンプレートが見つかりません: $TEMPLATE"
  exit 1
fi

sed "s/\${DOMAIN}/$DOMAIN/g" "$TEMPLATE" > "$CONF"
echo "✅  nginx/nginx.conf を生成しました (ドメイン: $DOMAIN)"

# ── 2. .env の FRONTEND_URL / CORS_ORIGINS を更新 ─────────────────────────
ENV_FILE="$ROOT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "⚠️   .env が見つかりません。.env.example からコピーします..."
  cp "$ROOT_DIR/.env.example" "$ENV_FILE"
  echo "✅  .env を作成しました。APIキーを入力してください"
fi

# FRONTEND_URL を置換（既存の値を上書き）
if grep -q '^FRONTEND_URL=' "$ENV_FILE"; then
  sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=https://$DOMAIN|" "$ENV_FILE"
else
  echo "FRONTEND_URL=https://$DOMAIN" >> "$ENV_FILE"
fi

# NEXT_PUBLIC_SITE_URL を置換
if grep -q '^NEXT_PUBLIC_SITE_URL=' "$ENV_FILE"; then
  sed -i "s|^NEXT_PUBLIC_SITE_URL=.*|NEXT_PUBLIC_SITE_URL=https://$DOMAIN|" "$ENV_FILE"
else
  echo "NEXT_PUBLIC_SITE_URL=https://$DOMAIN" >> "$ENV_FILE"
fi

# CORS_ORIGINS を置換
if grep -q '^CORS_ORIGINS=' "$ENV_FILE"; then
  sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://$DOMAIN,https://www.$DOMAIN|" "$ENV_FILE"
else
  echo "CORS_ORIGINS=https://$DOMAIN,https://www.$DOMAIN" >> "$ENV_FILE"
fi

echo "✅  .env の FRONTEND_URL / NEXT_PUBLIC_SITE_URL / CORS_ORIGINS を更新しました"

# ── 3. まとめ ─────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉  ドメイン設定が完了しました！"
echo ""
echo "次のステップ:"
echo "  1. .env に APIキーを入力してください"
echo "     nano .env"
echo ""
echo "  2. SSL証明書を取得してください"
echo "     make ssl-init DOMAIN=$DOMAIN EMAIL=admin@$DOMAIN"
echo ""
echo "  3. 本番起動"
echo "     make prod-build"
echo "     make migrate"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
