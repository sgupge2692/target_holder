#!/bin/bash
# GitHub Actions Self-hosted Runner セットアップスクリプト
# 対象OS: macOS / Linux (Ubuntu/Debian)
#
# 使い方:
#   1. GitHubリポジトリ Settings → Actions → Runners → New self-hosted runner
#   2. 表示される TOKEN をコピー
#   3. このスクリプトを実行:
#      GITHUB_REPO=sgupge2692/target_holder RUNNER_TOKEN=xxxxx bash scripts/setup_runner.sh

set -euo pipefail

REPO="${GITHUB_REPO:-sgupge2692/target_holder}"
TOKEN="${RUNNER_TOKEN:-}"
RUNNER_VERSION="2.317.0"
RUNNER_DIR="${HOME}/actions-runner"

# ── カラー出力 ──────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 前提チェック ────────────────────────────────────────
if [[ -z "$TOKEN" ]]; then
  error "RUNNER_TOKEN が未設定です。GitHubの Settings → Actions → Runners から取得してください。"
fi

if ! command -v docker &>/dev/null; then
  error "Docker がインストールされていません。先にインストールしてください。"
fi

if ! command -v docker compose &>/dev/null && ! docker compose version &>/dev/null; then
  error "Docker Compose がインストールされていません。"
fi

info "GitHub Actions Self-hosted Runner セットアップを開始します"
info "リポジトリ: https://github.com/${REPO}"

# ── OS判定 ──────────────────────────────────────────────
OS=$(uname -s)
ARCH=$(uname -m)

if [[ "$OS" == "Darwin" ]]; then
  RUNNER_OS="osx"
  if [[ "$ARCH" == "arm64" ]]; then
    RUNNER_ARCH="arm64"
  else
    RUNNER_ARCH="x64"
  fi
elif [[ "$OS" == "Linux" ]]; then
  RUNNER_OS="linux"
  if [[ "$ARCH" == "aarch64" ]] || [[ "$ARCH" == "arm64" ]]; then
    RUNNER_ARCH="arm64"
  else
    RUNNER_ARCH="x64"
  fi
else
  error "未対応OS: $OS (Windows は公式インストーラーを使ってください)"
fi

RUNNER_FILE="actions-runner-${RUNNER_OS}-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
DOWNLOAD_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_FILE}"

info "Runner: ${RUNNER_OS}/${RUNNER_ARCH} v${RUNNER_VERSION}"

# ── ダウンロード & 展開 ──────────────────────────────────
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

if [[ ! -f "$RUNNER_FILE" ]]; then
  info "Runnerをダウンロード中..."
  curl -fsSL -o "$RUNNER_FILE" "$DOWNLOAD_URL"
fi

info "展開中..."
tar xzf "$RUNNER_FILE"

# ── 設定 ────────────────────────────────────────────────
info "Runnerを設定中..."
./config.sh \
  --url "https://github.com/${REPO}" \
  --token "$TOKEN" \
  --name "$(hostname)-local" \
  --labels "self-hosted,${RUNNER_OS},${RUNNER_ARCH},stock-intelligence" \
  --work "_work" \
  --unattended \
  --replace

info "設定完了"

# ── サービスとして登録（バックグラウンド常駐） ────────────────
if [[ "$OS" == "Darwin" ]]; then
  # macOS: launchd
  info "macOSサービスとして登録中..."
  ./svc.sh install
  ./svc.sh start
  info "サービス開始: ./svc.sh status で確認できます"

elif [[ "$OS" == "Linux" ]]; then
  # Linux: systemd
  info "systemdサービスとして登録中..."
  sudo ./svc.sh install
  sudo ./svc.sh start
  info "サービス開始: sudo ./svc.sh status で確認できます"
fi

# ── 環境変数ファイルのセットアップ ──────────────────────────
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ ! -f "${REPO_DIR}/.env" ]]; then
  warn ".envファイルが見つかりません。.env.exampleからコピーしてAPIキーを設定してください:"
  warn "  cp ${REPO_DIR}/.env.example ${REPO_DIR}/.env"
  warn "  # .envを編集してJQUANTS_API_KEYなどを設定"
fi

echo ""
info "========================================================"
info "✅ Self-hosted Runner のセットアップが完了しました！"
info ""
info "Runner名: $(hostname)-local"
info "ラベル:   self-hosted, ${RUNNER_OS}, ${RUNNER_ARCH}, stock-intelligence"
info ""
info "GitHub Actions のスケジュール:"
info "  - 毎日 15:35 JST (月〜金): daily_pipeline.yml"
info "  - 毎週土曜 1:00 JST:       weekly_retrain.yml"
info ""
info "確認: https://github.com/${REPO}/settings/actions/runners"
info "========================================================"
