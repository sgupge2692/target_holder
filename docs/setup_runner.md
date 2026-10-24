# Self-hosted Runner セットアップ手順

GitHub Actions の CI/CD パイプラインをローカルPCで自動実行するための設定。

## なぜ Self-hosted Runner が必要か

- GitHub の標準ランナー（ubuntu-latest）はインターネット上のサーバーで動く
- 本プロジェクトはモデルファイルやDB等をローカルに保持する方針のため、自分のPCで動かす必要がある
- Self-hosted runner を設定すると、GitHubがスケジュール（cron）を管理しつつ、実行はローカルPCで行われる

## 前提条件

- Docker Desktop が起動している
- Docker Compose が使える（`docker compose version` で確認）
- `docker compose up` でサービスが起動済みであること

## セットアップ手順

### 1. GitHub でトークンを取得

1. リポジトリページ → **Settings** → **Actions** → **Runners**
2. **New self-hosted runner** をクリック
3. OSを選択（Mac/Linux/Windows）
4. 画面に表示される `--token xxxxx` の部分をコピー

### 2. スクリプトを実行

```bash
# リポジトリのルートディレクトリで実行
GITHUB_REPO=sgupge2692/target_holder \
RUNNER_TOKEN=<コピーしたトークン> \
bash scripts/setup_runner.sh
```

スクリプトが行うこと:
- GitHub Actions Runner のバイナリをダウンロード
- リポジトリに登録（ラベル: `self-hosted, stock-intelligence`）
- OS のサービスとして登録（PC再起動後も自動起動）

### 3. 動作確認

```bash
# GitHub上でランナーが "Idle" になっているか確認
# → Settings → Actions → Runners

# ローカルでサービス状態を確認
cd ~/actions-runner

# macOS
./svc.sh status

# Linux
sudo ./svc.sh status
```

### 4. Slack 通知の設定（任意）

GitHub リポジトリの **Settings** → **Secrets and variables** → **Actions** で以下を追加:

| Secret名 | 値 |
|---|---|
| `SLACK_WEBHOOK_URL` | Slack の Incoming Webhook URL |

Slack Webhook の作成: https://api.slack.com/messaging/webhooks

---

## スケジュール一覧

| ワークフロー | 実行タイミング | 内容 |
|---|---|---|
| `daily_pipeline.yml` | 平日 15:35 JST | データ取得 → 特徴量計算 → 差分学習 → 予測 |
| `weekly_retrain.yml` | 毎週土曜 1:00 JST | フルデータ取得 → フル再学習 → バックテスト |

---

## トラブルシューティング

### Runner が Offline になる

PC がスリープしてランナーが止まっている場合:

```bash
cd ~/actions-runner

# 手動起動
# macOS
./svc.sh start

# Linux
sudo ./svc.sh start
```

macOS でスリープさせないようにする:
```bash
# カフェインモード（電源接続時はスリープしない）
sudo pmset -c sleep 0
```

### Docker コンテナが起動していない

ランナーはDockerコンテナに `docker compose exec` でコマンドを送るため、
先にコンテナを起動しておく必要がある:

```bash
cd /path/to/target_holder
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### ワークフローを手動実行したい

GitHub の Actions タブ → 対象ワークフロー → **Run workflow** で手動実行できる。

---

## アンインストール

```bash
cd ~/actions-runner

# サービス停止・削除
# macOS
./svc.sh stop
./svc.sh uninstall

# Linux
sudo ./svc.sh stop
sudo ./svc.sh uninstall

# GitHub から登録解除
./config.sh remove --token <新しいトークン>
```
