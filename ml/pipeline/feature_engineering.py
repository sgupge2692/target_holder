"""
テクニカル指標・特徴量を計算してDBに保存するスクリプト
"""
import os
import numpy as np
import pandas as pd
import talib
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def load_quotes(engine, code: str = None) -> pd.DataFrame:
    """DBから日足データを取得"""
    query = "SELECT * FROM daily_quotes"
    if code:
        query += f" WHERE \"Code\" = '{code}'"
    query += " ORDER BY \"Code\", \"Date\""
    return pd.read_sql(query, engine)


def calc_features(df: pd.DataFrame) -> pd.DataFrame:
    """テクニカル指標を計算"""
    close = df["Close"].values.astype(float)
    high = df["High"].values.astype(float)
    low = df["Low"].values.astype(float)
    volume = df["Volume"].values.astype(float)

    # 移動平均との乖離率
    for period in [5, 25, 75]:
        ma = talib.SMA(close, timeperiod=period)
        df[f"ma{period}_deviation"] = (close - ma) / ma

    # ゴールデン/デッドクロスフラグ
    ma5 = talib.SMA(close, timeperiod=5)
    ma25 = talib.SMA(close, timeperiod=25)
    df["golden_cross"] = ((ma5 > ma25) & (np.roll(ma5, 1) <= np.roll(ma25, 1))).astype(int)
    df["dead_cross"] = ((ma5 < ma25) & (np.roll(ma5, 1) >= np.roll(ma25, 1))).astype(int)

    # ボリンジャーバンド
    upper, middle, lower = talib.BBANDS(close, timeperiod=20)
    df["bb_percent_b"] = (close - lower) / (upper - lower)
    df["bb_width"] = (upper - lower) / middle

    # RSI
    df["rsi"] = talib.RSI(close, timeperiod=14)

    # MACD
    macd, signal, _ = talib.MACD(close)
    df["macd_diff"] = macd - signal

    # 出来高移動平均比
    vol_ma = talib.SMA(volume, timeperiod=25)
    df["volume_ratio"] = volume / vol_ma

    # 価格上昇×出来高増加フラグ
    df["price_up_vol_up"] = (
        (close > np.roll(close, 1)) & (volume > vol_ma)
    ).astype(int)

    # 過去20日の日次リターン系列
    for i in range(1, 21):
        df[f"return_lag{i}"] = (close - np.roll(close, i)) / np.roll(close, i)

    # ローソク足の実体・ヒゲ比率
    body = abs(df["Close"] - df["Open"])
    full_range = df["High"] - df["Low"]
    df["body_ratio"] = body / full_range.replace(0, np.nan)
    df["upper_shadow"] = (df["High"] - df[["Close", "Open"]].max(axis=1)) / full_range.replace(0, np.nan)
    df["lower_shadow"] = (df[["Close", "Open"]].min(axis=1) - df["Low"]) / full_range.replace(0, np.nan)

    # 翌日騰落ラベル（目的変数）
    df["next_return"] = (np.roll(close, -1) - close) / close
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
