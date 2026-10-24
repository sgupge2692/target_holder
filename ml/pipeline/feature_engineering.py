"""
テクニカル指標・特徴量を計算してDBに保存するスクリプト

列名はfetch_data.py (v2対応) のsnake_case形式に対応:
  code, date, open, high, low, close, volume, adj_close, adj_volume, ...
"""
import os
import numpy as np
import pandas as pd
import talib
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# 特徴量カラム定義（train.py / predict.py と共有）
FEATURE_COLS = [
    "ma5_deviation", "ma25_deviation", "ma75_deviation",
    "golden_cross", "dead_cross",
    "bb_percent_b", "bb_width",
    "rsi", "macd_diff",
    "volume_ratio", "price_up_vol_up",
    "body_ratio", "upper_shadow", "lower_shadow",
] + [f"ret_lag_{i}" for i in range(1, 21)]  # DB列名に合わせてret_lag_N形式


def load_quotes(engine, code: str = None) -> pd.DataFrame:
    """DBから日足データを取得（v2対応のsnake_case列名）"""
    if code:
        query = text("SELECT * FROM daily_quotes WHERE code = :code ORDER BY date")
        df = pd.read_sql(query, engine, params={"code": code})
    else:
        query = text("SELECT * FROM daily_quotes ORDER BY code, date")
        df = pd.read_sql(query, engine)
    return df


def calc_features(df: pd.DataFrame) -> pd.DataFrame:
    """テクニカル指標を計算（入力: snake_case列名のDataFrame）"""
    # 調整済み終値が使えればそちらを優先
    if "adj_close" in df.columns and df["adj_close"].notna().any():
        close = df["adj_close"].values.astype(float)
        open_ = df["adj_open"].values.astype(float)
        high  = df["adj_high"].values.astype(float)
        low   = df["adj_low"].values.astype(float)
        vol   = df["adj_volume"].fillna(df["volume"]).values.astype(float)
    else:
        close = df["close"].values.astype(float)
        open_ = df["open"].values.astype(float)
        high  = df["high"].values.astype(float)
        low   = df["low"].values.astype(float)
        vol   = df["volume"].values.astype(float)

    feat = df[["code", "date"]].copy()

    # --- トレンド系 ---
    for period in [5, 25, 75]:
        ma = talib.SMA(close, timeperiod=period)
        feat[f"ma{period}_deviation"] = (close - ma) / ma

    ma5  = talib.SMA(close, timeperiod=5)
    ma25 = talib.SMA(close, timeperiod=25)
    feat["golden_cross"] = ((ma5 > ma25) & (np.roll(ma5, 1) <= np.roll(ma25, 1))).astype(int)
    feat["dead_cross"]   = ((ma5 < ma25) & (np.roll(ma5, 1) >= np.roll(ma25, 1))).astype(int)

    # --- ボリンジャーバンド ---
    upper, middle, lower = talib.BBANDS(close, timeperiod=20)
    band_range = upper - lower
    feat["bb_percent_b"] = np.where(band_range != 0, (close - lower) / band_range, 0.5)
    feat["bb_width"]     = np.where(middle != 0, band_range / middle, np.nan)

    # --- オシレーター ---
    feat["rsi"]       = talib.RSI(close, timeperiod=14)
    macd, sig, _      = talib.MACD(close)
    feat["macd_diff"] = macd - sig

    # --- 出来高 ---
    vol_ma = talib.SMA(vol, timeperiod=25)
    feat["volume_ratio"]    = np.where(vol_ma != 0, vol / vol_ma, np.nan)
    feat["price_up_vol_up"] = (
        (close > np.roll(close, 1)) & (vol > vol_ma)
    ).astype(int)

    # --- 過去20日のリターンラグ ---
    for i in range(1, 21):
        prev = np.roll(close, i)
        feat[f"ret_lag_{i}"] = np.where(prev != 0, (close - prev) / prev, np.nan)

    # --- ローソク足形状 ---
    body       = np.abs(close - open_)
    full_range = high - low
    feat["body_ratio"]   = np.where(full_range != 0, body / full_range, np.nan)
    feat["upper_shadow"] = np.where(full_range != 0,
        (high - np.maximum(close, open_)) / full_range, np.nan)
    feat["lower_shadow"] = np.where(full_range != 0,
        (np.minimum(close, open_) - low) / full_range, np.nan)

    # --- ラベル（目的変数） ---
    next_close        = np.roll(close, -1)
    feat["next_return"] = np.where(close != 0, (next_close - close) / close, np.nan)
    feat["label"]       = 0
    feat.loc[feat["next_return"] >  0.01, "label"] =  1   # 翌日+1%超: 上昇
    feat.loc[feat["next_return"] < -0.01, "label"] = -1   # 翌日-1%超: 下落
    # 最終行は翌日データがないのでNaN → dropna で除去
    feat.iloc[-1, feat.columns.get_loc("next_return")] = np.nan

    return feat.dropna(subset=["rsi", "macd_diff", "next_return"])  # 最低限のNA除去


def save_features(df: pd.DataFrame, engine):
    """featuresテーブルにupsert"""
    with engine.begin() as conn:
        df.to_sql("_tmp_features", conn, if_exists="replace", index=False)
        conn.execute(text("""
            INSERT INTO features
            SELECT * FROM _tmp_features
            ON CONFLICT (code, date) DO UPDATE SET
                ma5_deviation   = EXCLUDED.ma5_deviation,
                ma25_deviation  = EXCLUDED.ma25_deviation,
                ma75_deviation  = EXCLUDED.ma75_deviation,
                golden_cross    = EXCLUDED.golden_cross,
                dead_cross      = EXCLUDED.dead_cross,
                bb_percent_b    = EXCLUDED.bb_percent_b,
                bb_width        = EXCLUDED.bb_width,
                rsi             = EXCLUDED.rsi,
                macd_diff       = EXCLUDED.macd_diff,
                volume_ratio    = EXCLUDED.volume_ratio,
                price_up_vol_up = EXCLUDED.price_up_vol_up,
                body_ratio      = EXCLUDED.body_ratio,
                upper_shadow    = EXCLUDED.upper_shadow,
                lower_shadow    = EXCLUDED.lower_shadow,
                next_return     = EXCLUDED.next_return,
                label           = EXCLUDED.label
        """))
        conn.execute(text("DROP TABLE _tmp_features"))
    print(f"  {len(df)} 行を features にupsert完了")


def main():
    engine = create_engine(DATABASE_URL)
    df_quotes = load_quotes(engine)
    print(f"日足データ読み込み: {len(df_quotes)} 行")

    results = []
    codes = df_quotes["code"].unique()
    print(f"対象銘柄数: {len(codes)}")

    for i, code in enumerate(codes):
        group = df_quotes[df_quotes["code"] == code].copy().reset_index(drop=True)
        if len(group) < 80:  # 75日MAを計算するには最低80日必要
            continue
        try:
            feat = calc_features(group)
            results.append(feat)
        except Exception as e:
            print(f"  {code} エラー: {e}")

        if i % 100 == 0:
            print(f"  {i}/{len(codes)} 処理済み...")

    if results:
        df_all = pd.concat(results, ignore_index=True)
        print(f"特徴量計算完了: {len(df_all)} 行")
        save_features(df_all, engine)
    else:
        print("特徴量が生成されませんでした。日足データを確認してください。")


if __name__ == "__main__":
    main()
