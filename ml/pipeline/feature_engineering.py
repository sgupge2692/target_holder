"""
テクニカル指標・特徴量を計算してDBに保存するスクリプト
純 pandas 実装（TA-Lib 不要）

v3 改善:
  - ATRベース動的ラベル閾値（銘柄ごとのボラに応じた閾値）
  - カレンダー特徴量（曜日・月末・月初・四半期）
  - セクター相対特徴量（同セクター比）
  - 市場全体相対特徴量（全銘柄平均比）

v4 改善:
  - ニュースセンチメント特徴量（Yahoo Finance Japan RSS）
    環境変数 NEWS_SENTIMENT=true でオン（デフォルト: オフ）

v5 改善:
  - ギャップアップ/ダウン（前日終値との開き）
  - 出来高急増フラグ（3σ超）
  - ローリングボラティリティ（5/20日）
  - 52週高値・安値からの乖離率（価格位置）
  - 連続上昇/下落日数（モメンタムストリーク）
  - 高値更新・安値更新フラグ
"""
import os
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
USE_NEWS_SENTIMENT = os.getenv("NEWS_SENTIMENT", "false").lower() == "true"


# ────────────────────────────────────────────────────────────────
# 基本指標
# ────────────────────────────────────────────────────────────────

def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def bbands(series: pd.Series, period: int = 20, std: float = 2.0):
    middle = sma(series, period)
    std_val = series.rolling(window=period).std()
    upper = middle + std * std_val
    lower = middle - std * std_val
    return upper, middle, lower

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line

def vwap(close: pd.Series, high: pd.Series, low: pd.Series, volume: pd.Series, period: int = 20) -> pd.Series:
    typical_price = (high + low + close) / 3
    tp_vol = typical_price * volume
    return tp_vol.rolling(window=period).sum() / volume.rolling(window=period).sum()

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()

def roc(series: pd.Series, period: int = 10) -> pd.Series:
    return (series - series.shift(period)) / series.shift(period)

def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    highest_high = high.rolling(window=period).max()
    lowest_low   = low.rolling(window=period).min()
    return -100 * (highest_high - close) / (highest_high - lowest_low).replace(0, np.nan)

def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3):
    lowest_low   = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    d = k.rolling(window=d_period).mean()
    return k, d


# ────────────────────────────────────────────────────────────────
# DB ロード
# ────────────────────────────────────────────────────────────────

def load_quotes(engine) -> pd.DataFrame:
    """daily_quotes + listed_stocks(sector_code) を JOIN して取得"""
    query = """
        SELECT q.*, s.sector_code
        FROM daily_quotes q
        LEFT JOIN listed_stocks s ON s.code = q."Code"
        ORDER BY q."Code", q."Date"
    """
    df = pd.read_sql(query, engine)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


# ────────────────────────────────────────────────────────────────
# 個別銘柄特徴量
# ────────────────────────────────────────────────────────────────

def calc_features_single(df: pd.DataFrame) -> pd.DataFrame:
    """1銘柄のテクニカル特徴量（セクター相対は後でまとめて計算）"""
    close  = df["Close"].astype(float)
    high   = df["High"].astype(float)
    low    = df["Low"].astype(float)
    volume = df["Volume"].astype(float)
    open_  = df["Open"].astype(float)

    # ── 移動平均乖離率 ────────────────────────────────────────
    for period in [5, 25, 75]:
        ma = sma(close, period)
        df[f"ma{period}_deviation"] = (close - ma) / ma

    # ── ゴールデン/デッドクロス ─────────────────────────────
    ma5  = sma(close, 5)
    ma25 = sma(close, 25)
    df["golden_cross"] = ((ma5 > ma25) & (ma5.shift(1) <= ma25.shift(1))).astype(int)
    df["dead_cross"]   = ((ma5 < ma25) & (ma5.shift(1) >= ma25.shift(1))).astype(int)

    # ── ボリンジャーバンド ────────────────────────────────────
    upper, middle, lower = bbands(close, period=20)
    df["bb_percent_b"] = (close - lower) / (upper - lower).replace(0, np.nan)
    df["bb_width"]     = (upper - lower) / middle.replace(0, np.nan)

    # ── RSI ──────────────────────────────────────────────────
    df["rsi"] = rsi(close, period=14)

    # ── MACD ─────────────────────────────────────────────────
    macd_line, signal_line = macd(close)
    df["macd_diff"] = macd_line - signal_line

    # ── 出来高 ────────────────────────────────────────────────
    vol_ma = sma(volume, 25)
    df["volume_ratio"]    = volume / vol_ma.replace(0, np.nan)
    df["price_up_vol_up"] = ((close > close.shift(1)) & (volume > vol_ma)).astype(int)

    # ── ラグリターン ──────────────────────────────────────────
    for i in range(1, 21):
        df[f"return_lag{i}"] = (close - close.shift(i)) / close.shift(i)

    # ── ローソク足 ────────────────────────────────────────────
    body       = (close - open_).abs()
    full_range = (high - low).replace(0, np.nan)
    df["body_ratio"]   = body / full_range
    df["upper_shadow"] = (high - df[["Close", "Open"]].max(axis=1)) / full_range
    df["lower_shadow"] = (df[["Close", "Open"]].min(axis=1) - low) / full_range

    # ── VWAP 乖離率 ───────────────────────────────────────────
    vwap_val = vwap(close, high, low, volume, period=20)
    df["vwap_deviation"] = (close - vwap_val) / vwap_val.replace(0, np.nan)

    # ── ATR 比率 ──────────────────────────────────────────────
    atr_val = atr(high, low, close, period=14)
    df["atr_ratio"] = atr_val / close.replace(0, np.nan)

    # ── OBV トレンド ──────────────────────────────────────────
    obv_val   = obv(close, volume)
    obv_ema20 = ema(obv_val, 20)
    df["obv_trend"] = (obv_val - obv_ema20) / obv_ema20.abs().replace(0, np.nan)

    # ── 出来高モメンタム ──────────────────────────────────────
    df["volume_momentum"] = roc(volume, period=5)

    # ── RoC ──────────────────────────────────────────────────
    df["roc_5"]  = roc(close, period=5)
    df["roc_20"] = roc(close, period=20)

    # ── Williams %R ──────────────────────────────────────────
    df["williams_r"] = williams_r(high, low, close, period=14)

    # ── Stochastic ────────────────────────────────────────────
    k, d = stochastic(high, low, close)
    df["stoch_k"]    = k
    df["stoch_d"]    = d
    df["stoch_diff"] = k - d

    # ── カレンダー特徴量 ──────────────────────────────────────
    date_col = pd.to_datetime(df["Date"])
    df["day_of_week"]   = date_col.dt.dayofweek.astype(int)      # 0=月 4=金
    df["is_monday"]     = (date_col.dt.dayofweek == 0).astype(int)
    df["is_friday"]     = (date_col.dt.dayofweek == 4).astype(int)
    df["month"]         = date_col.dt.month.astype(int)
    df["quarter"]       = date_col.dt.quarter.astype(int)
    # 月末3営業日フラグ（日付から近似）
    df["is_month_end"]   = (date_col.dt.is_month_end |
                            (date_col + pd.offsets.BDay(1)).dt.is_month_end |
                            (date_col + pd.offsets.BDay(2)).dt.is_month_end).astype(int)
    df["is_month_start"] = (date_col.dt.is_month_start |
                            (date_col - pd.offsets.BDay(1)).dt.is_month_start |
                            (date_col - pd.offsets.BDay(2)).dt.is_month_start).astype(int)

    # ── v5 追加特徴量 ─────────────────────────────────────────

    # ギャップアップ/ダウン（前日終値 vs 当日始値）
    df["gap_up"]   = ((open_ - close.shift(1)) / close.shift(1)).clip(lower=0)
    df["gap_down"] = ((close.shift(1) - open_) / close.shift(1)).clip(lower=0)
    df["gap"]      = (open_ - close.shift(1)) / close.shift(1)

    # 出来高急増フラグ（過去25日の平均+3σ超）
    vol_std = volume.rolling(window=25).std()
    df["volume_spike"] = (volume > (vol_ma + 3 * vol_std)).astype(int)
    df["volume_spike_ratio"] = (volume - vol_ma) / vol_std.replace(0, np.nan)  # σ倍率

    # ローリングボラティリティ（リターンの標準偏差）
    daily_return = close.pct_change()
    df["volatility_5d"]  = daily_return.rolling(window=5).std()
    df["volatility_20d"] = daily_return.rolling(window=20).std()

    # 52週（約250営業日）高値・安値からの乖離（価格位置）
    high_52w = high.rolling(window=250, min_periods=60).max()
    low_52w  = low.rolling(window=250, min_periods=60).min()
    df["dist_from_high_52w"] = (close - high_52w) / high_52w.replace(0, np.nan)  # 負の値
    df["dist_from_low_52w"]  = (close - low_52w)  / low_52w.replace(0, np.nan)   # 正の値
    # 52週レンジ内の位置（0=安値、1=高値）
    range_52w = (high_52w - low_52w).replace(0, np.nan)
    df["price_position_52w"] = (close - low_52w) / range_52w

    # 連続上昇/下落日数（モメンタムストリーク）
    direction = np.sign(daily_return.fillna(0))
    streak_up   = []
    streak_down = []
    cnt_up = cnt_down = 0
    for d in direction:
        if d > 0:
            cnt_up += 1; cnt_down = 0
        elif d < 0:
            cnt_down += 1; cnt_up = 0
        else:
            cnt_up = cnt_down = 0
        streak_up.append(cnt_up)
        streak_down.append(cnt_down)
    df["streak_up"]   = streak_up
    df["streak_down"] = streak_down

    # 高値更新・安値更新フラグ（20日・60日）
    for window in [20, 60]:
        df[f"new_high_{window}d"] = (close == close.rolling(window).max()).astype(int)
        df[f"new_low_{window}d"]  = (close == close.rolling(window).min()).astype(int)

    # ── ATRベース動的ラベル ───────────────────────────────────
    next_close        = close.shift(-1)
    df["next_return"] = (next_close - close) / close

    # ATR(14) / Close を閾値として使用（最小 0.5%、最大 3%）
    dynamic_threshold = atr_val / close.replace(0, np.nan)
    dynamic_threshold = dynamic_threshold.clip(lower=0.005, upper=0.03)

    df["label"] = 0
    df.loc[df["next_return"] >  dynamic_threshold, "label"] =  1
    df.loc[df["next_return"] < -dynamic_threshold, "label"] = -1

    return df


# ────────────────────────────────────────────────────────────────
# セクター・市場相対特徴量（全銘柄まとめて計算）
# ────────────────────────────────────────────────────────────────

def add_relative_features(df_all: pd.DataFrame) -> pd.DataFrame:
    """
    セクター相対特徴量と市場全体相対特徴量を追加。
    df_all は全銘柄の特徴量を結合した DataFrame。
    """
    df_all = df_all.copy()
    df_all["Date"] = pd.to_datetime(df_all["Date"])

    # 日次リターン（return_lag1 を流用）
    df_all["return_1d"] = df_all["return_lag1"]

    # ── 市場全体相対特徴量 ────────────────────────────────────
    market_mean = (
        df_all.groupby("Date")["return_1d"]
        .transform("median")
    )
    df_all["market_relative_return"] = df_all["return_1d"] - market_mean

    market_rsi = df_all.groupby("Date")["rsi"].transform("median")
    df_all["market_relative_rsi"] = df_all["rsi"] - market_rsi

    # ── セクター相対特徴量 ─────────────────────────────────────
    if "sector_code" in df_all.columns and df_all["sector_code"].notna().any():
        sector_return = (
            df_all.groupby(["Date", "sector_code"])["return_1d"]
            .transform("median")
        )
        df_all["sector_relative_return"] = df_all["return_1d"] - sector_return

        sector_rsi = (
            df_all.groupby(["Date", "sector_code"])["rsi"]
            .transform("median")
        )
        df_all["sector_relative_rsi"] = df_all["rsi"] - sector_rsi

        sector_ma5 = (
            df_all.groupby(["Date", "sector_code"])["ma5_deviation"]
            .transform("median")
        )
        df_all["sector_relative_ma5"] = df_all["ma5_deviation"] - sector_ma5
    else:
        # セクター情報なし → 0 埋め
        df_all["sector_relative_return"] = 0.0
        df_all["sector_relative_rsi"]    = 0.0
        df_all["sector_relative_ma5"]    = 0.0

    return df_all


# ────────────────────────────────────────────────────────────────
# エントリポイント
# ────────────────────────────────────────────────────────────────

def add_news_sentiment(df_all: pd.DataFrame) -> pd.DataFrame:
    """
    最新日のニュースセンチメントを各銘柄に付与する。
    USE_NEWS_SENTIMENT=true の時のみ実行。ネットワーク不可時は 0 埋め。
    """
    if not USE_NEWS_SENTIMENT:
        df_all["news_sentiment"]     = 0.0
        df_all["news_pos_count"]     = 0
        df_all["news_neg_count"]     = 0
        df_all["news_article_count"] = 0
        return df_all

    try:
        from news_sentiment import build_news_features_df

        # listed_stocks から社名を取得（あれば）
        codes = df_all["Code"].unique().tolist()
        code_name_map = {}
        if "CompanyName" in df_all.columns:
            code_name_map = df_all.groupby("Code")["CompanyName"].first().to_dict()

        codes_names = [(c, code_name_map.get(c, c)) for c in codes]
        print(f"Fetching news sentiment for {len(codes_names)} stocks...")
        news_df = build_news_features_df(codes_names, sleep_sec=0.3)
        df_all = df_all.merge(news_df, on="Code", how="left")

        # 欠損は 0 埋め
        for col in ["news_sentiment", "news_pos_count", "news_neg_count", "news_article_count"]:
            df_all[col] = df_all[col].fillna(0)

        print(f"News sentiment attached. avg={df_all['news_sentiment'].mean():.4f}")
    except Exception as e:
        print(f"News sentiment failed ({e}), filling zeros.")
        df_all["news_sentiment"]     = 0.0
        df_all["news_pos_count"]     = 0
        df_all["news_neg_count"]     = 0
        df_all["news_article_count"] = 0

    return df_all


def main():
    engine = create_engine(DATABASE_URL)
    df = load_quotes(engine)
    print(f"Loaded {len(df)} rows")

    # 1. 個別銘柄の特徴量計算
    results = []
    for code, group in df.groupby("Code"):
        try:
            features = calc_features_single(group.copy())
            results.append(features)
        except Exception as e:
            print(f"Error processing {code}: {e}")

    if not results:
        print("特徴量の計算結果がありません。")
        return

    df_all = pd.concat(results, ignore_index=True)

    # 2. セクター・市場相対特徴量を追加（全銘柄まとめて）
    df_all = add_relative_features(df_all)

    # 3. ニュースセンチメント特徴量（NEWS_SENTIMENT=true の時のみ）
    df_all = add_news_sentiment(df_all)

    df_all = df_all.dropna(subset=["label"])
    df_all.to_sql("features", engine, if_exists="replace", index=False)
    print(f"Saved {len(df_all)} rows to features")

    # ラベル分布を表示
    dist = df_all["label"].value_counts().sort_index()
    total = len(df_all)
    print(f"Label distribution: UP={dist.get(1,0)} ({dist.get(1,0)/total:.1%}), "
          f"DOWN={dist.get(-1,0)} ({dist.get(-1,0)/total:.1%}), "
          f"NEUTRAL={dist.get(0,0)} ({dist.get(0,0)/total:.1%})")


if __name__ == "__main__":
    main()
