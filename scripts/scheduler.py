#!/usr/bin/env python3
"""
軽量スケジューラ（コンテナ内で動かす cron の代わり）

なぜ作ったか:
  以前の cron コンテナは、Debian 系イメージに無い `crond` と Alpine 用のパス（/etc/crontabs）を前提にしており、
  非 root ユーザーでは書き込めず、タイムゾーンも UTC のままで、そもそも動かなかった。
  標準ライブラリだけで動き、日本時間（JST 固定。日本は夏時間が無い）で実行する。

使い方:
  python scripts/scheduler.py --file ml/schedule.txt
  python scripts/scheduler.py --file ml/schedule.txt --list      # 次回の実行時刻を表示して終了

スケジュールファイルの書式（# で始まる行はコメント）:
  HH:MM  曜日  コマンド
  曜日: 1-5（月〜金）/ 6 / 1,3,5 / * のように、1=月 … 7=日
  例:  17:30  1-5  python pipeline/run_daily.py
"""
from __future__ import annotations

import argparse
import logging
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
logger = logging.getLogger("scheduler")


@dataclass(frozen=True)
class Job:
    hour: int
    minute: int
    days: frozenset          # ISO 曜日（1=月 … 7=日）
    command: str

    def is_due(self, now: datetime) -> bool:
        return now.hour == self.hour and now.minute == self.minute and now.isoweekday() in self.days


def parse_days(spec: str) -> frozenset:
    """'1-5' / '6' / '1,3,5' / '*' → ISO 曜日の集合"""
    spec = spec.strip()
    if spec == "*":
        return frozenset(range(1, 8))
    days: set[int] = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
            if a > b:
                raise ValueError(f"曜日の範囲が逆です: {part}")
            days.update(range(a, b + 1))
        else:
            days.add(int(part))
    if not days or min(days) < 1 or max(days) > 7:
        raise ValueError(f"曜日は 1（月）〜7（日）で指定してください: {spec}")
    return frozenset(days)


def parse_schedule(text: str) -> list[Job]:
    jobs: list[Job] = []
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            raise ValueError(f"{no} 行目: 'HH:MM 曜日 コマンド' の形式で書いてください: {raw!r}")
        when, days, command = parts
        try:
            hh, mm = (int(x) for x in when.split(":"))
        except ValueError:
            raise ValueError(f"{no} 行目: 時刻は HH:MM で書いてください: {when!r}") from None
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError(f"{no} 行目: 時刻が範囲外です: {when!r}")
        try:
            jobs.append(Job(hh, mm, parse_days(days), command.strip()))
        except ValueError as e:
            raise ValueError(f"{no} 行目: {e}") from None
    return jobs


def next_run(job: Job, now: datetime) -> datetime:
    """now より後で、次にそのジョブが走る時刻"""
    base = now.replace(second=0, microsecond=0)
    for offset in range(0, 9):
        cand = (base + timedelta(days=offset)).replace(hour=job.hour, minute=job.minute)
        if cand > now and cand.isoweekday() in job.days:
            return cand
    raise ValueError("次回の実行時刻を求められません")


def run_job(job: Job, runner=subprocess.run, timeout_sec: int = 6 * 3600) -> int:
    """ジョブを実行して終了コードを返す。失敗しても例外は投げない（スケジューラを止めない）。"""
    logger.info("開始: %s", job.command)
    started = time.monotonic()
    try:
        proc = runner(shlex.split(job.command), timeout=timeout_sec)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        logger.error("タイムアウト（%d 秒）: %s", timeout_sec, job.command)
        return 124
    except Exception as e:  # コマンドが見つからない等
        logger.error("実行できません: %s (%s)", job.command, e)
        return 127
    level = logging.INFO if code == 0 else logging.ERROR
    logger.log(level, "終了(コード %s, %.0f 秒): %s", code, time.monotonic() - started, job.command)
    return code


def serve(jobs: list[Job], now_fn=lambda: datetime.now(JST), sleep_fn=time.sleep, max_ticks: int | None = None,
          runner=subprocess.run) -> None:
    """毎分、実行時刻になったジョブを順に実行する。同じ分に二重実行しない。"""
    last_minute = None
    ticks = 0
    while max_ticks is None or ticks < max_ticks:
        ticks += 1
        now = now_fn()
        key = now.replace(second=0, microsecond=0)
        if key != last_minute:
            last_minute = key
            for job in jobs:
                if job.is_due(now):
                    run_job(job, runner=runner)
        sleep_fn(max(1.0, 60 - now.second - now.microsecond / 1e6) if max_ticks is None else 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="JST で動く軽量スケジューラ")
    parser.add_argument("--file", required=True, help="スケジュールファイル")
    parser.add_argument("--list", action="store_true", help="次回の実行時刻を表示して終了")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with open(args.file, encoding="utf-8") as f:
        jobs = parse_schedule(f.read())
    if not jobs:
        logger.error("ジョブがありません: %s", args.file)
        return 1

    now = datetime.now(JST)
    for job in jobs:
        logger.info("登録: 次回 %s  %s", next_run(job, now).strftime("%Y-%m-%d %H:%M (%a) JST"), job.command)
    if args.list:
        return 0
    serve(jobs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
