"""
send_daily_signals.py のユニットテスト

実行方法:
  cd scripts && python -m pytest test_send_daily_signals.py -v
または
  pytest scripts/test_send_daily_signals.py -v
"""
import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

# DATABASE_URL をダミーに設定（import 時の接続を防ぐ）
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://dummy:dummy@localhost/dummy")

from scripts.send_daily_signals import _send_with_retry


# ── _send_with_retry のテスト ───────────────────────────────────────────

def test_send_with_retry_success_first_try():
    """初回で成功すればリトライしない"""
    with patch("scripts.send_daily_signals.send_email", return_value=True) as mock_send:
        result = _send_with_retry("user@example.com", "subject", "<p>html</p>", retries=3)
    assert result is True
    assert mock_send.call_count == 1


def test_send_with_retry_success_on_second_try():
    """1回失敗して2回目で成功"""
    responses = [False, True]
    with patch("scripts.send_daily_signals.send_email", side_effect=responses) as mock_send:
        with patch("scripts.send_daily_signals.time.sleep"):  # sleepをスキップ
            result = _send_with_retry("user@example.com", "subject", "<p>html</p>", retries=3)
    assert result is True
    assert mock_send.call_count == 2


def test_send_with_retry_all_fail():
    """全リトライが失敗する"""
    with patch("scripts.send_daily_signals.send_email", return_value=False) as mock_send:
        with patch("scripts.send_daily_signals.time.sleep"):
            result = _send_with_retry("user@example.com", "subject", "<p>html</p>", retries=3)
    assert result is False
    assert mock_send.call_count == 3


def test_send_with_retry_retries_1():
    """retries=1 のときは1回だけ試みる"""
    with patch("scripts.send_daily_signals.send_email", return_value=False) as mock_send:
        result = _send_with_retry("user@example.com", "subject", "<p>html</p>", retries=1)
    assert result is False
    assert mock_send.call_count == 1


def test_send_with_retry_exponential_backoff():
    """バックオフで sleep が呼ばれることを確認"""
    with patch("scripts.send_daily_signals.send_email", return_value=False):
        with patch("scripts.send_daily_signals.time.sleep") as mock_sleep:
            _send_with_retry("u@example.com", "s", "h", retries=3)
    # 1回目失敗→sleep(2), 2回目失敗→sleep(4), 3回目失敗→リトライなし
    assert mock_sleep.call_count == 2
    calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert calls == [2, 4]  # 2^1, 2^2


# ── fetch_today_signals のテスト ────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_today_signals_returns_list():
    """DBをモックして今日のシグナルが取得できることを確認"""
    from scripts.send_daily_signals import fetch_today_signals

    mock_row = MagicMock()
    mock_row.code = "7203"
    mock_row.company_name = "トヨタ自動車"
    mock_row.signal = "UP"
    mock_row.probability = 0.82
    mock_row.pred_date = "2026-10-31"

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    signals = await fetch_today_signals(mock_session, limit=10)
    assert len(signals) == 1
    assert signals[0]["code"] == "7203"
    assert signals[0]["signal"] == "UP"
    assert signals[0]["probability_pct"] == pytest.approx(82.0)


@pytest.mark.asyncio
async def test_fetch_today_signals_fallback_to_7days():
    """本日分がない場合は7日以内にフォールバック"""
    from scripts.send_daily_signals import fetch_today_signals

    mock_row = MagicMock()
    mock_row.code = "9984"
    mock_row.company_name = "SoftBank"
    mock_row.signal = "UP"
    mock_row.probability = 0.75
    mock_row.pred_date = "2026-10-30"

    # 1回目（今日）: 空、2回目（7日以内）: 1件
    mock_result_empty = MagicMock()
    mock_result_empty.fetchall.return_value = []
    mock_result_data = MagicMock()
    mock_result_data.fetchall.return_value = [mock_row]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[mock_result_empty, mock_result_data])

    signals = await fetch_today_signals(mock_session, limit=10)
    assert len(signals) == 1
    assert signals[0]["code"] == "9984"


# ── main の dry-run テスト ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_main_dry_run_does_not_send():
    """dry_run=True のときメールは送信されない"""
    from scripts.send_daily_signals import main

    mock_signals = [{"code": "7203", "company_name": "トヨタ", "signal": "UP", "probability_pct": 80.0, "pred_date": "2026-10-31"}]
    mock_user = MagicMock()
    mock_user.email = "pro@example.com"

    with patch("scripts.send_daily_signals.fetch_today_signals", new=AsyncMock(return_value=mock_signals)):
        with patch("scripts.send_daily_signals.fetch_accuracy", new=AsyncMock(return_value={})):
            with patch("scripts.send_daily_signals.get_alert_subscribers", new=AsyncMock(return_value=[mock_user])):
                with patch("scripts.send_daily_signals.create_async_engine"):
                    with patch("scripts.send_daily_signals.AsyncSession"):
                        with patch("scripts.send_daily_signals.send_email") as mock_send:
                            with patch("scripts.send_daily_signals.render_daily_signal_email", return_value="<html/>"):
                                # dry_run=True なのでメール送信されないはず
                                try:
                                    await main(dry_run=True, user_limit=1)
                                except SystemExit:
                                    pass
                                assert mock_send.call_count == 0


@pytest.mark.asyncio
async def test_main_with_limit():
    """user_limit で送信対象を絞れる"""
    from scripts.send_daily_signals import main

    mock_signals = [{"code": "7203", "company_name": "トヨタ", "signal": "UP", "probability_pct": 80.0, "pred_date": "2026-10-31"}]
    mock_users = [MagicMock(email=f"user{i}@example.com") for i in range(5)]

    with patch("scripts.send_daily_signals.fetch_today_signals", new=AsyncMock(return_value=mock_signals)):
        with patch("scripts.send_daily_signals.fetch_accuracy", new=AsyncMock(return_value={})):
            with patch("scripts.send_daily_signals.get_alert_subscribers", new=AsyncMock(return_value=mock_users)):
                with patch("scripts.send_daily_signals.create_async_engine"):
                    with patch("scripts.send_daily_signals.AsyncSession"):
                        with patch("scripts.send_daily_signals.send_email", return_value=True) as mock_send:
                            with patch("scripts.send_daily_signals.render_daily_signal_email", return_value="<html/>"):
                                with patch("scripts.send_daily_signals.time.sleep"):
                                    try:
                                        await main(dry_run=False, user_limit=2)
                                    except SystemExit:
                                        pass
                                    # 5人いても2人にしか送らない
                                    assert mock_send.call_count == 2
