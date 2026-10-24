"""
翌日騰落予測を実行してDBに保存するスクリプト

毎日15:35のパイプラインで実行される。
60%以上の確度のシグナルのみDBに記録する。
"""
import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_DIR    = os.getenv("MODEL_DIR", "/app/models")

# feature_engineering.py / train.py と同一定義
FEATURE_COLS = [
    "ma5_deviation", "ma25_deviation", "ma75_deviation",
    "golden_cross", "dead_cross",
    "bb_percent_b", "bb_width",
    "rsi", "macd_diff",
    "volume_ratio", "price_up_vol_up",
    "body_ratio", "upper_shadow", "lower_shadow",
] + [f"ret_lag_{i}" for i in range(1, 21)]

CONFIDENCE_THRESHOLD = 0.60  # 60%以上の確度のみシグナルを出す


def main():
    engine = create_engine(DATABASE_URL)

    model  = joblib.load(f"{MODEL_DIR}/lgbm_model.pkl")
    scaler = joblib.load(f"{MODEL_DIR}/scaler.pkl")

    # 各銘柄の最新特徴量を取得
    df = pd.read_sql(
        text("""
            SELECT DISTINCT ON (code) *
            FROM features
            ORDER BY code, date DESC
        """),
        engine
    )
    print(f"予測対象銘柄: {len(df)} 件")

    X = df[FEATURE_COLS].replace([np.inf, -np.inf], np.nan)
    valid_idx = X.dropna().index
    X_valid   = X.loc[valid_idx]
    X_scaled  = scaler.transform(X_valid)

    proba = model.predict_proba(X_scaled)  # [[P(下落), P(上昇)], ...]
    df_valid = df.loc[valid_idx].copy()
    df_valid["up_probability"] = proba[:, 1]
    df_valid["signal"] = np.where(
        df_valid["up_probability"] >= CONFIDENCE_THRESHOLD,       "UP",
        np.where(df_valid["up_probability"] <= (1 - CONFIDENCE_THRESHOLD), "DOWN", "HOLD")
    )
    df_valid["predicted_at"] = datetime.now()

    # HOLD を除いたシグナルのみ保存
    signals = df_valid[df_valid["signal"] != "HOLD"][
        ["code", "date", "up_probability", "signal", "predicted_at"]
    ].copy()

    up_count   = (signals["signal"] == "UP").sum()
    down_count = (signals["signal"] == "DOWN").sum()
    print(f"シグナル: UP={up_count}, DOWN={down_count}, HOLD={len(df_valid) - len(signals)}")

    if signals.empty:
        print("本日のシグナルはありません。")
        return

    # ON CONFLICT DO NOTHING でduplicateを安全に無視
    with engine.begin() as conn:
        signals.to_sql("_tmp_predictions", conn, if_exists="replace", index=False)
        result = conn.execute(text("""
            INSERT INTO predictions (code, date, up_probability, signal, predicted_at)
            SELECT code, date, up_probability, signal, predicted_at
            FROM _tmp_predictions
            ON CONFLICT (code, date) DO NOTHING
        """))
        conn.execute(text("DROP TABLE _tmp_predictions"))
        print(f"{result.rowcount} 件を predictions に保存しました。")


if __name__ == "__main__":
    main()
