"""スケジューラのテスト（時刻は固定して、実際には待たない）"""
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from scheduler import JST, Job, next_run, parse_days, parse_schedule, run_job, serve

JST_ = timezone(timedelta(hours=9))


def test_parse_days():
    assert parse_days("1-5") == frozenset({1, 2, 3, 4, 5})
    assert parse_days("6") == frozenset({6})
    assert parse_days("1,3,5") == frozenset({1, 3, 5})
    assert parse_days("*") == frozenset(range(1, 8))
    for bad in ("0", "8", "5-1", "a"):
        with pytest.raises(ValueError):
            parse_days(bad)


def test_parse_schedule_skips_comments_and_reports_line_numbers():
    jobs = parse_schedule("# 日次\n\n17:30  1-5  python pipeline/run_daily.py --x\n01:00 6 python a.py\n")
    assert [(j.hour, j.minute, j.command) for j in jobs] == [
        (17, 30, "python pipeline/run_daily.py --x"), (1, 0, "python a.py")]
    with pytest.raises(ValueError, match="2 行目"):
        parse_schedule("17:30 1-5 ok\n25:00 1-5 bad")
    with pytest.raises(ValueError, match="1 行目"):
        parse_schedule("17:30 1-5")


def test_is_due_uses_jst_weekday():
    job = Job(17, 30, parse_days("1-5"), "x")
    assert job.is_due(datetime(2026, 11, 10, 17, 30, 5, tzinfo=JST_))        # 火曜
    assert not job.is_due(datetime(2026, 11, 14, 17, 30, tzinfo=JST_))       # 土曜
    assert not job.is_due(datetime(2026, 11, 10, 17, 31, tzinfo=JST_))


def test_next_run_skips_weekend():
    job = Job(17, 30, parse_days("1-5"), "x")
    fri_evening = datetime(2026, 11, 13, 18, 0, tzinfo=JST_)                  # 金曜 18:00
    assert next_run(job, fri_evening) == datetime(2026, 11, 16, 17, 30, tzinfo=JST_)   # 月曜
    assert next_run(job, datetime(2026, 11, 10, 9, 0, tzinfo=JST_)) == datetime(2026, 11, 10, 17, 30, tzinfo=JST_)


def test_run_job_reports_exit_code_and_never_raises():
    class P:  # subprocess.run の戻り値の代わり
        def __init__(self, rc): self.returncode = rc
    assert run_job(Job(0, 0, parse_days("*"), "echo hi"), runner=lambda *a, **k: P(0)) == 0
    assert run_job(Job(0, 0, parse_days("*"), "x"), runner=lambda *a, **k: P(3)) == 3

    def boom(*a, **k): raise FileNotFoundError("no such command")
    assert run_job(Job(0, 0, parse_days("*"), "nope"), runner=boom) == 127

    def slow(*a, **k): raise subprocess.TimeoutExpired("x", 1)
    assert run_job(Job(0, 0, parse_days("*"), "slow"), runner=slow) == 124


def test_serve_runs_due_jobs_once_per_minute_in_order():
    ran = []
    jobs = [Job(17, 30, parse_days("1-5"), "first"), Job(17, 30, parse_days("1-5"), "second"),
            Job(18, 0, parse_days("1-5"), "later")]

    class P: returncode = 0
    def runner(cmd, timeout=None): ran.append(cmd[0]); return P()

    base = datetime(2026, 11, 10, 17, 30, 0, tzinfo=JST_)
    times = iter([base, base + timedelta(seconds=20), base + timedelta(seconds=50),     # 同じ分に3回見ても1回だけ
                  base + timedelta(minutes=1), base + timedelta(minutes=30)])
    serve(jobs, now_fn=lambda: next(times), sleep_fn=lambda s: None, max_ticks=5, runner=runner)
    assert ran == ["first", "second", "later"]


def test_failed_job_does_not_stop_the_next_one():
    ran = []
    class P:
        def __init__(self, rc): self.returncode = rc
    def runner(cmd, timeout=None):
        ran.append(cmd[0]); return P(1 if cmd[0] == "bad" else 0)
    jobs = [Job(9, 0, parse_days("*"), "bad"), Job(9, 0, parse_days("*"), "good")]
    serve(jobs, now_fn=lambda: datetime(2026, 11, 10, 9, 0, tzinfo=JST_), sleep_fn=lambda s: None, max_ticks=1, runner=runner)
    assert ran == ["bad", "good"]
