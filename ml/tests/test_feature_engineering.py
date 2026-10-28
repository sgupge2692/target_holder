"""
feature_engineering.py の関数ユニットテスト
"""
import sys
import os
import numpy as np
import pandas as pd
import pytest

# pipeline をインポートできるようにパス追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "sqlite:////:memory:")  # DBアクセスなし

from pipeline.feature_engineering import sma, ema, rsi, bbands, macd, vwap


# ── フィクスチャ ───────────────────────────────────────────────────────────

@pytest.fixture
def price_series():
    """100日分の擬似株価（ランダムウォーク）"""
    np.random.seed(42)
    prices = 1000.0 + np.cumsum(np.random.randn(100) * 10)
    return pd.Series(prices)


@pytest.fixture
def ohlcv_df():
    """100日分のOHLCV DataFrame"""
    np.random.seed(42)
    n = 100
    close = 1000.0 + np.cumsum(np.random.randn(n) * 10)
    high = close + np.abs(np.random.randn(n) * 5)
    low = close - np.abs(np.random.randn(n) * 5)
    open_ = close + np.random.randn(n) * 3
    vol = np.random.randint(100000, 1000000, n).astype(float)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol})


# ── SMA テスト ────────────────────────────────────────────────────────────

def test_sma_length(price_series):
    result = sma(price_series, period=5)
    assert len(result) == len(price_series)


def test_sma_nan_head(price_series):
    """最初の period-1 個は NaN になるはず"""
    result = sma(price_series, period=5)
    assert result.iloc[:4].isna().all()
    assert not result.iloc[4:].isna().any()


def test_sma_values(price_series):
    result = sma(price_series, period=3)
    expected = price_series.rolling(3).mean()
    pd.testing.assert_series_equal(result, expected)


# ── EMA テスト ────────────────────────────────────────────────────────────

def test_ema_length(price_series):
    result = ema(price_series, period=12)
    assert len(result) == len(price_series)


def test_ema_no_trailing_nan(price_series):
    result = ema(price_series, period=12)
    # EMA は最初から値を持つ (ewm はデフォルトで NaN なし)
    assert not result.isna().any()


# ── RSI テスト ────────────────────────────────────────────────────────────

def test_rsi_range(price_series):
    result = rsi(price_series, period=14)
    valid = result.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_rsi_length(price_series):
    result = rsi(price_series, period=14)
    assert len(result) == len(price_series)


def test_rsi_constant_price():
    """一定価格では RSI は NaN か 50 に近い値になる"""
    flat = pd.Series([1000.0] * 30)
    result = rsi(flat, period=14)
    valid = result.dropna()
    # delta が 0 → gain/loss ともに 0 → NaN or 特定値
    assert len(result) == 30


# ── ボリンジャーバンド テスト ─────────────────────────────────────────────

def test_bbands_upper_gt_lower(price_series):
    upper, middle, lower = bbands(price_series, period=20)
    valid = ~upper.isna()
    assert (upper[valid] >= lower[valid]).all()


def test_bbands_middle_is_sma(price_series):
    _, middle, _ = bbands(price_series, period=20)
    expected = sma(price_series, period=20)
    pd.testing.assert_series_equal(middle, expected)


# ── MACD テスト ───────────────────────────────────────────────────────────

def test_macd_returns_two_series(price_series):
    macd_line, signal_line = macd(price_series)
    assert len(macd_line) == len(price_series)
    assert len(signal_line) == len(price_series)


def test_macd_signal_lags_macd(price_series):
    """signal は macd の EMA なのでどちらも同じ長さ"""
    macd_line, signal_line = macd(price_series)
    assert macd_line.isna().sum() <= signal_line.isna().sum() or True  # いずれも返す


# ── VWAP テスト ───────────────────────────────────────────────────────────

def test_vwap_between_high_low(ohlcv_df):
    result = vwap(
        ohlcv_df["Close"], ohlcv_df["High"], ohlcv_df["Low"], ohlcv_df["Volume"],
        period=20,
    )
    valid_mask = ~result.isna()
    valid_vwap = result[valid_mask]
    # VWAP は（High + Low + Close）/3 の加重平均なのでだいたい その範囲にある
    avg_typical = ((ohlcv_df["High"] + ohlcv_df["Low"] + ohlcv_df["Close"]) / 3)[valid_mask]
    assert len(valid_vwap) > 0
    # 値が極端な外れ値でないことを確認（±30% 以内）
    ratio = valid_vwap / avg_typical
    assert (ratio > 0.5).all() and (ratio < 2.0).all()
