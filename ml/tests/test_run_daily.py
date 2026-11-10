"""日次パイプラインの実行順序・失敗時の扱い・休場日の扱いのテスト（実際のスクリプトは動かさない）"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from pipeline.run_daily import DAILY_STEPS, WEEKLY_STEPS, already_predicted, notify_failure, run_pipeline


class Recorder:
    def __init__(self, fail=()):
        self.calls, self.fail, self.notes = [], set(fail), []

    def __call__(self, args):
        self.calls.append(args[0].split("/")[-1])
        return 1 if args[0].split("/")[-1] in self.fail else 0

    def notify(self, msg):
        self.notes.append(msg)


def test_daily_order_and_all_steps_run():
    r = Recorder()
    assert run_pipeline(DAILY_STEPS, r, r.notify) == 0
    assert r.calls == ["fetch_data.py", "collect_news.py", "feature_engineering.py", "train.py", "predict.py", "backtest.py"]
    assert r.notes == []


def test_news_before_features_and_features_before_predict():
    names = [s.args[0].split("/")[-1] for s in DAILY_STEPS]
    assert names.index("collect_news.py") < names.index("feature_engineering.py") < names.index("predict.py")
    assert names.index("fetch_data.py") == 0


@pytest.mark.parametrize("failing", ["fetch_data.py", "feature_engineering.py", "predict.py"])
def test_required_failure_stops_and_notifies(failing):
    r = Recorder(fail=[failing])
    assert run_pipeline(DAILY_STEPS, r, r.notify) == 1
    assert r.calls[-1] == failing                      # 以降は実行しない
    assert len(r.notes) == 1 and "失敗" in r.notes[0]


def test_stale_features_are_never_used_for_predict():
    """特徴量の計算が失敗したら、古い特徴量で予測しない"""
    r = Recorder(fail=["feature_engineering.py"])
    run_pipeline(DAILY_STEPS, r, r.notify)
    assert "predict.py" not in r.calls


@pytest.mark.parametrize("failing", ["collect_news.py", "train.py", "backtest.py"])
def test_optional_failure_continues_and_warns(failing):
    r = Recorder(fail=[failing])
    assert run_pipeline(DAILY_STEPS, r, r.notify) == 0
    assert "predict.py" in r.calls and len(r.calls) == len(DAILY_STEPS)
    assert len(r.notes) == 1 and failing.split(".")[0] in "".join(s.args[0] for s in DAILY_STEPS if failing in s.args[0])


def test_skip_when_already_predicted_after_fetch():
    r = Recorder()
    assert run_pipeline(DAILY_STEPS, r, r.notify, skip_if_done=lambda: "2026-11-09") == 0
    assert r.calls == ["fetch_data.py"]                # 取得だけして終了。予測を二重に作らない
    assert r.notes == []


def test_not_skipped_when_new_day_available_or_fetch_failed():
    r = Recorder()
    run_pipeline(DAILY_STEPS, r, r.notify, skip_if_done=lambda: None)
    assert len(r.calls) == len(DAILY_STEPS)
    r2 = Recorder(fail=["fetch_data.py"])
    assert run_pipeline(DAILY_STEPS, r2, r2.notify, skip_if_done=lambda: "2026-11-09") == 1   # 取得失敗はスキップ扱いにしない


def test_weekly_steps_do_full_fetch_and_full_train():
    flat = [" ".join(s.args) for s in WEEKLY_STEPS]
    assert any("fetch_data.py --full" in f for f in flat) and any("train.py --mode full" in f for f in flat)
    assert not any("predict.py" in f for f in flat)


def test_already_predicted_logic():
    from sqlalchemy import create_engine, text
    e = create_engine("sqlite://")
    with e.begin() as c:
        c.execute(text('CREATE TABLE daily_quotes ("Date" TEXT)'))
        c.execute(text('CREATE TABLE predictions ("Date" TEXT)'))
    assert already_predicted(e) is None                                  # どちらも空
    with e.begin() as c:
        c.execute(text("INSERT INTO daily_quotes VALUES ('2026-11-09')"))
    assert already_predicted(e) is None                                  # 株価だけ（予測が無い）
    with e.begin() as c:
        c.execute(text("INSERT INTO predictions VALUES ('2026-11-06')"))
    assert already_predicted(e) is None                                  # 予測が古い → 新しい日がある
    with e.begin() as c:
        c.execute(text("INSERT INTO predictions VALUES ('2026-11-09')"))
    assert already_predicted(e) == "2026-11-09"                          # 最新日は予測済み
    assert already_predicted(create_engine("sqlite://")) is None         # テーブルが無くても落ちない


def test_notify_without_webhook_or_on_error_never_raises():
    assert notify_failure("x", webhook="") is False
    def boom(*a, **k): raise OSError("down")
    assert notify_failure("x", webhook="http://example.invalid", post=boom) is False
    sent = []
    assert notify_failure("x", webhook="http://example.invalid", post=lambda req, timeout=None: sent.append(req)) is True
    assert b'"text"' in sent[0].data
