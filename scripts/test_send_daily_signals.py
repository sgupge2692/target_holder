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


# ── DB まわり（モックではなく実際の SQL を SQLite で動かす） ─────────────────
# モックだと、存在しない列名を参照していても気づけない（実際にそれで本番では失敗していた）。

from datetime import date, timedelta
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession as RealSession, create_async_engine as real_engine


async def _make_session():
    engine = real_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(sa_text("CREATE TABLE listed_stocks (code TEXT PRIMARY KEY, company_name TEXT)"))
        await conn.execute(sa_text('''CREATE TABLE predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, "Code" TEXT, "Date" TEXT,
            up_probability REAL, signal TEXT, is_correct INTEGER)'''))
        await conn.execute(sa_text("CREATE TABLE watchlist (id INTEGER PRIMARY KEY, user_id INTEGER, code TEXT, company_name TEXT)"))
    return engine, RealSession(engine)


async def _add_pred(session, code, d, prob, sig, ok=None):
    await session.execute(
        sa_text('INSERT INTO predictions ("Code","Date",up_probability,signal,is_correct) VALUES (:c,:d,:p,:s,:ok)'),
        {"c": code, "d": d.isoformat(), "p": prob, "s": sig, "ok": ok},
    )


@pytest.mark.asyncio
async def test_fetch_today_signals_latest_day_up_only_sorted():
    from scripts.send_daily_signals import fetch_today_signals
    engine, session = await _make_session()
    today, yday = date.today(), date.today() - timedelta(days=1)
    await session.execute(sa_text("INSERT INTO listed_stocks VALUES ('7203','トヨタ自動車')"))
    await _add_pred(session, "7203", today, 0.58, "UP")
    await _add_pred(session, "9984", today, 0.62, "UP")
    await _add_pred(session, "6758", today, 0.40, "DOWN")      # DOWN は含めない
    await _add_pred(session, "1111", yday, 0.99, "UP")         # 古い日は含めない
    await session.commit()

    signals = await fetch_today_signals(session, limit=10)
    assert [s["code"] for s in signals] == ["9984", "7203"]    # 確度の高い順
    assert signals[1]["company_name"] == "トヨタ自動車"
    assert signals[0]["company_name"] == "9984"                # 名前が無ければコード
    assert signals[0]["probability_pct"] == pytest.approx(62.0)
    assert signals[0]["pred_date"] == today.isoformat()
    await session.close(); await engine.dispose()


@pytest.mark.asyncio
async def test_fetch_today_signals_empty_table():
    from scripts.send_daily_signals import fetch_today_signals
    engine, session = await _make_session()
    assert await fetch_today_signals(session) == []
    await session.close(); await engine.dispose()


@pytest.mark.asyncio
async def test_fetch_accuracy_requires_enough_samples():
    from scripts.send_daily_signals import fetch_accuracy, MIN_ACCURACY_SAMPLES
    engine, session = await _make_session()
    d = date.today() - timedelta(days=3)
    for i in range(MIN_ACCURACY_SAMPLES - 1):
        await _add_pred(session, f"{i}", d, 0.6, "UP", ok=1)
    await session.commit()
    assert await fetch_accuracy(session) == {}                 # 母数不足なら出さない

    await _add_pred(session, "x", d, 0.6, "UP", ok=0)
    await session.commit()
    acc = await fetch_accuracy(session)
    assert acc["UP"]["total"] == MIN_ACCURACY_SAMPLES
    assert acc["UP"]["accuracy_pct"] == pytest.approx((MIN_ACCURACY_SAMPLES - 1) * 100 / MIN_ACCURACY_SAMPLES)
    await session.close(); await engine.dispose()


@pytest.mark.asyncio
async def test_fetch_watch_changes_only_flipped_and_grouped_by_user():
    from scripts.send_daily_signals import fetch_watch_changes
    engine, session = await _make_session()
    today, yday = date.today(), date.today() - timedelta(days=1)
    await session.execute(sa_text("INSERT INTO listed_stocks VALUES ('7203','トヨタ自動車')"))
    # 7203: NEUTRAL → UP（変化）、9984: UP → UP（変化なし）、6758: 前回なし、4063: NEUTRAL → NEUTRAL
    for code, prev, now in [("7203", "NEUTRAL", "UP"), ("9984", "UP", "UP"), ("4063", "NEUTRAL", "NEUTRAL")]:
        await _add_pred(session, code, yday, 0.5, prev)
        await _add_pred(session, code, today, 0.6, now)
    await _add_pred(session, "6758", today, 0.6, "UP")
    for uid, code in [(1, "7203"), (1, "9984"), (2, "7203"), (2, "6758"), (2, "4063")]:
        await session.execute(sa_text("INSERT INTO watchlist (user_id, code) VALUES (:u,:c)"), {"u": uid, "c": code})
    await session.commit()

    changes = await fetch_watch_changes(session, today)
    assert set(changes) == {1, 2}
    assert [c["code"] for c in changes[1]] == ["7203"]
    assert changes[1][0]["prev_signal"] == "NEUTRAL" and changes[1][0]["signal"] == "UP"
    assert changes[1][0]["company_name"] == "トヨタ自動車"
    assert [c["code"] for c in changes[2]] == ["7203"]         # 前回なし・中立のままは含めない
    await session.close(); await engine.dispose()


def test_render_email_includes_watch_changes_and_relative_wording():
    from app.notifications import render_daily_signal_email
    html = render_daily_signal_email(
        date="2026-11-09",
        signals=[{"code": "7203", "company_name": "トヨタ", "signal": "UP", "probability_pct": 58.0}],
        accuracy_pct=52.3, accuracy_n=120,
        watch_changes=[{"code": "9984", "company_name": "SB", "prev_signal": "UP", "signal": "DOWN", "probability_pct": 41.0}],
    )
    assert "ウォッチ中の銘柄に変化があります" in html
    assert "市場より強い" in html and "市場より弱い" in html
    assert "n=120" in html and "投資助言・売買の推奨ではありません" in html
    plain = render_daily_signal_email(date="2026-11-09", signals=[])
    assert "ウォッチ中の銘柄に変化があります" not in plain


# ── main の dry-run テスト ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_main_dry_run_does_not_send():
    """dry_run=True のときメールは送信されない"""
    from scripts.send_daily_signals import main

    mock_signals = [{"code": "7203", "company_name": "トヨタ", "signal": "UP", "probability_pct": 80.0, "pred_date": date.today().isoformat()}]
    mock_user = MagicMock()
    mock_user.email = "pro@example.com"

    mock_engine = AsyncMock()
    with patch("scripts.send_daily_signals.fetch_today_signals", new=AsyncMock(return_value=mock_signals)):
        with patch("scripts.send_daily_signals.fetch_accuracy", new=AsyncMock(return_value={})), patch("scripts.send_daily_signals.fetch_watch_changes", new=AsyncMock(return_value={})):
            with patch("scripts.send_daily_signals.get_alert_subscribers", new=AsyncMock(return_value=[mock_user])):
                with patch("scripts.send_daily_signals.create_async_engine", return_value=mock_engine):
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

    mock_signals = [{"code": "7203", "company_name": "トヨタ", "signal": "UP", "probability_pct": 80.0, "pred_date": date.today().isoformat()}]
    mock_users = [MagicMock(email=f"user{i}@example.com") for i in range(5)]

    mock_engine2 = AsyncMock()
    with patch("scripts.send_daily_signals.fetch_today_signals", new=AsyncMock(return_value=mock_signals)):
        with patch("scripts.send_daily_signals.fetch_accuracy", new=AsyncMock(return_value={})), patch("scripts.send_daily_signals.fetch_watch_changes", new=AsyncMock(return_value={})):
            with patch("scripts.send_daily_signals.get_alert_subscribers", new=AsyncMock(return_value=mock_users)):
                with patch("scripts.send_daily_signals.create_async_engine", return_value=mock_engine2):
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
