"""
テクニカル指標・特徴量を計算してDBに保存するスクリプト
pandas-ta を使用（コンパイル不要）
"""
import os
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


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


def load_quotes(engine, code: str = None) -> pd.DataFrame:
    """DBから日足データを取得"""
    query = "SELECT * FROM daily_quotes"
    if code:
        query += f" WHERE \"Code\" = '{code}'"
    query += " ORDER BY \"Code\", \"Date\""
    return pd.read_sql(query, engine)


def calc_features(df: pd.DataFrame) -> pd.DataFrame:
    """テクニカル指標を計算"""
    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    volume = df["Volume"].astype(float)

    # 移動平均との乖離率
    for period in [5, 25, 75]:
        ma = sma(close, period)
        df[f"ma{period}_deviation"] = (close - ma) / ma

    # ゴールデン/デッドクロスフラグ
    ma5 = sma(close, 5)
    ma25 = sma(close, 25)
    df["golden_cross"] = ((ma5 > ma25) & (ma5.shift(1) <= ma25.shift(1))).astype(int)
    df["dead_cross"] = ((ma5 < ma25) & (ma5.shift(1) >= ma25.shift(1))).astype(int)

    # ボリンジャーバンド
    upper, middle, lower = bbands(close, period=20)
    df["bb_percent_b"] = (close - lower) / (upper - lower)
    df["bb_width"] = (upper - lower) / middle

    # RSI
    df["rsi"] = rsi(close, period=14)

    # MACD
    macd_line, signal_line = macd(close)
    df["macd_diff"] = macd_line - signal_line

    # 出来高移動平均比
    vol_ma = sma(volume, 25)
    df["volume_ratio"] = volume / vol_ma

    # 価格上昇×出来高増加フラグ
    df["price_up_vol_up"] = (
        (close > close.shift(1)) & (volume > vol_ma)
    ).astype(int)

    # 過去20日の日次リターン系列
    for i in range(1, 21):
        df[f"return_lag{i}"] = (close - close.shift(i)) / close.shift(i)

    # ローソク足の実体・ヒゲ比率
    body = (df["Close"] - df["Open"]).abs()
    full_range = (df["High"] - df["Low"]).replace(0, np.nan)
    df["body_ratio"] = body / full_range
    df["upper_shadow"] = (df["High"] - df[["Close", "Open"]].max(axis=1)) / full_range
    df["lower_shadow"] = (df[["Close", "Open"]].min(axis=1) - df["Low"]) / full_range

    # 翌日騰落ラベル（目的変数）
    next_close = close.shift(-1)
    df["next_return"] = (next_close - close) / close
    df["label"] = 0
    df.loc[df["next_return"] > 0.01, "label"] = 1   # +1%以上: 上昇
    df.loc[df["next_return"] < -0.01, "label"] = -1  # -1%以下: 下落

    return df.dropna()


def main():
    engine = create_engine(DATABASE_URL)
    df = load_quotes(engine)
    print(f"Loaded {len(df)} rows")

    results = []
    for code, group in df.groupby("Code"):
        try:
            features = calc_features(group.copy())
            results.append(features)
        except Exception as e:
            print(f"Error processing {code}: {e}")

    if results:
        df_all = pd.concat(results, ignore_index=True)
        df_all.to_sql("features", engine, if_exists="replace", index=False)
        print(f"Saved {len(df_all)} rows to features")


if __name__ == "__main__":
    main()
