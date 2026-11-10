"""
日次 / 週次パイプラインの実行（これが「毎日の流れ」の唯一の定義）

  python pipeline/run_daily.py            # 日次: 取得 → ニュース収集 → 特徴量 → 逐次学習 → 予測 → 実績記録
  python pipeline/run_daily.py --weekly   # 週次: 全データ取得 → 特徴量 → フル再学習 → 実績記録
  python pipeline/run_daily.py --force    # 「予測済み」でも最後まで実行する
  python pipeline/run_daily.py --dry-run  # 実行内容だけ表示

ステップには「必須」と「任意」がある。
  必須が失敗 → 以降を実行せず終了コード 1（古い特徴量や古いモデルで予測して、古い情報を新しく見せない）
  任意が失敗 → 警告を出して続行（ニュース収集・逐次学習・実績記録は、失敗しても予測は出せる）

休場日・データ未公開の日の扱い:
  最新の株価日にすでに予測があれば、そこで終了する（同じ日の予測を二重に作らない）。
  データの公開が遅れた日は、スケジュールで時間を空けて 2 回目を走らせれば、1 回目は何もせず終わり、2 回目で処理される。

失敗の通知: 環境変数 SLACK_WEBHOOK_URL があれば Slack に送る。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.dirname(HERE)


@dataclass(frozen=True)
class Step:
    name: str
    args: tuple          # python のあとに渡す引数
    required: bool = True


DAILY_STEPS = [
    Step("データ取得",   ("pipeline/fetch_data.py",)),
    # ニュースは 18:00 JST より前に収集する（news_store.py）。失敗しても予測は止めない。
    Step("ニュース収集", ("pipeline/collect_news.py",), required=False),
    Step("特徴量計算",   ("pipeline/feature_engineering.py",)),
    Step("逐次学習",     ("pipeline/train.py", "--mode", "incremental"), required=False),
    Step("予測",         ("pipeline/predict.py",)),
    Step("実績記録",     ("pipeline/backtest.py",), required=False),
]

WEEKLY_STEPS = [
    Step("全データ取得", ("pipeline/fetch_data.py", "--full")),
    Step("特徴量計算",   ("pipeline/feature_engineering.py",)),
    Step("フル再学習",   ("pipeline/train.py", "--mode", "full")),
    Step("実績記録",     ("pipeline/backtest.py",), required=False),
]


def default_runner(args: tuple) -> int:
    return subprocess.run([sys.executable, *args], cwd=ML_DIR).returncode


def already_predicted(engine) -> Optional[str]:
    """最新の株価日にすでに予測があればその日付（YYYY-MM-DD）、無ければ None。DB が読めなければ None。"""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            quote = conn.execute(text('SELECT MAX("Date") FROM daily_quotes')).scalar()
            pred = conn.execute(text('SELECT MAX("Date") FROM predictions')).scalar()
    except Exception:
        return None
    if quote is None or pred is None:
        return None
    return str(quote)[:10] if str(pred)[:10] >= str(quote)[:10] else None


def notify_failure(message: str, webhook: Optional[str] = None, post: Callable = None) -> bool:
    """Slack に失敗を送る。送れなくても例外は投げない。送ったら True。"""
    webhook = webhook or os.getenv("SLACK_WEBHOOK_URL", "")
    if not webhook:
        return False
    try:
        req = urllib.request.Request(
            webhook, data=json.dumps({"text": message}).encode(),
            headers={"Content-type": "application/json"}, method="POST")
        (post or urllib.request.urlopen)(req, timeout=10)
        return True
    except Exception as e:
        print(f"[run] Slack 通知に失敗: {e}")
        return False


def run_pipeline(
    steps: list[Step],
    runner: Callable[[tuple], int] = default_runner,
    notify: Callable[[str], object] = notify_failure,
    skip_if_done: Optional[Callable[[], Optional[str]]] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """
    ステップを順に実行する。終了コード 0=成功（または実行済みで何もしなかった）、1=必須ステップの失敗。

    skip_if_done: 「すでに予測済みか」を返す関数（日付 or None）。取得の直後に呼び、済みなら残りを実行しない。
    """
    failed_optional: list[str] = []
    for i, step in enumerate(steps):
        t0 = time.monotonic()
        print(f"[run] ▶ {step.name}: python {' '.join(step.args)}", flush=True)
        code = runner(step.args)
        print(f"[run] {'✓' if code == 0 else '✗'} {step.name}（{time.monotonic() - t0:.0f} 秒, コード {code}）", flush=True)

        if code != 0:
            if step.required:
                msg = f"❌ 日次パイプライン失敗: 「{step.name}」が終了コード {code}。以降は実行していません。"
                print(f"[run] {msg}")
                notify(msg)
                return 1
            failed_optional.append(step.name)
            print(f"[run] ⚠ 任意のステップが失敗しましたが続行します: {step.name}")

        # 取得の直後: 最新の株価日にすでに予測があれば、休場日・実行済みなので終了する
        if i == 0 and skip_if_done is not None and code == 0:
            done = skip_if_done()
            if done:
                print(f"[run] 最新の株価日 {done} は予測済み（休場日・データ未公開・実行済み）。ここで終了します。")
                return 0

    if failed_optional:
        notify(f"⚠ 日次パイプラインは完了しましたが、次の任意ステップが失敗しました: {', '.join(failed_optional)}")
    print("[run] すべて完了しました。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="日次 / 週次パイプライン")
    parser.add_argument("--weekly", action="store_true", help="週次（全データ取得・フル再学習）")
    parser.add_argument("--force", action="store_true", help="予測済みでも最後まで実行する")
    parser.add_argument("--dry-run", action="store_true", help="実行内容だけ表示する")
    args = parser.parse_args()

    steps = WEEKLY_STEPS if args.weekly else DAILY_STEPS
    if args.dry_run:
        for s in steps:
            print(f"{'必須' if s.required else '任意'}  {s.name}: python {' '.join(s.args)}")
        return 0

    skip = None
    if not args.weekly and not args.force:
        from sqlalchemy import create_engine
        engine = create_engine(os.environ["DATABASE_URL"])
        skip = lambda: already_predicted(engine)  # noqa: E731
    return run_pipeline(steps, skip_if_done=skip)


if __name__ == "__main__":
    sys.exit(main())
