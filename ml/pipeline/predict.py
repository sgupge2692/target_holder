"""
翌日騰落予測を実行してDBに保存するスクリプト
"""
import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_DIR = "/app/models"

FEATURE_COLS = [
    "ma5_deviation", "ma25_deviation", "ma75_deviation",
    "golden_cross", "dead_cross",
    "bb_percent_b", "bb_width",
    "rsi", "macd_diff",
    "volume_ratio", "price_up_vol_up",
    "body_ratio", "upper_shadow", "lower_shadow",
] + [f"return_lag{i}" for i in range(1, 21)]

CONFIDENCE_THRESHOLD = 0.60  # 60%以上の確度のみシグナルを出す


def main():
    engine = create_engine(DATABASE_URL)

    model = joblib.load(f"{MODEL_DIR}/lgbm_model.pkl")
    scaler = joblib.load(f"{MODEL_DIR}/scaler.pkl")

    # 最新の特徴量を取得
    df = pd.read_sql(
        "SELECT * FROM features ORDER BY \"Date\" DESC LIMIT 10000",
        engine
    )

    # 各銘柄の最新行のみ取得
    latest = df.sort_values("Date").groupby("Code").last().reset_index()

    X = latest[FEATURE_COLS].replace([np.inf, -np.inf], np.nan)
    valid_idx = X.dropna().index
    X_valid = X.loc[valid_idx]
    X_scaled = scaler.transform(X_valid)

    proba = model.predict_proba(X_scaled)
    latest_valid = latest.loc[valid_idx].copy()
    latest_valid["up_probability"] = proba[:, 1]
    latest_valid["signal"] = np.where(
        latest_valid["up_probability"] >= CONFIDENCE_THRESHOLD, "UP",
        np.where(latest_valid["up_probability"] <= (1 - CONFIDENCE_THRESHOLD), "DOWN", "NEUTRAL")
    )
    latest_valid["predicted_at"] = datetime.now()

    # シグナルのみDBに保存
    signals = latest_valid[latest_valid["signal"] != "NEUTRAL"][
        ["Code", "Date", "up_probability", "signal", "predicted_at"]
    ]

    signals.to_sql("predictions", engine, if_exists="append", index=False)
    print(f"Saved {len(signals)} signals (UP: {(signals['signal']=='UP').sum()}, DOWN: {(signals['signal']=='DOWN').sum()})")


if __name__ == "__main__":
    main()
