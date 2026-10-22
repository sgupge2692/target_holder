"""
モデル学習スクリプト
--mode full: フル再学習（週次）
--mode incremental: 逐次学習（日次）
"""
import os
import argparse
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from lightgbm import LGBMClassifier
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_DIR = "/app/models"
os.makedirs(MODEL_DIR, exist_ok=True)

FEATURE_COLS = [
    "ma5_deviation", "ma25_deviation", "ma75_deviation",
    "golden_cross", "dead_cross",
    "bb_percent_b", "bb_width",
    "rsi", "macd_diff",
    "volume_ratio", "price_up_vol_up",
    "body_ratio", "upper_shadow", "lower_shadow",
] + [f"return_lag{i}" for i in range(1, 21)]


def load_features(engine) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM features", engine)


def train_full(df: pd.DataFrame):
    """フル再学習"""
    X = df[FEATURE_COLS].replace([np.inf, -np.inf], np.nan).dropna()
    y = df.loc[X.index, "label"]

    # ラベル0（中立）を除外して上昇/下落のみ学習
    mask = y != 0
    X, y = X[mask], y[mask]
    y = (y == 1).astype(int)  # 1: 上昇, 0: 下落

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LGBMClassifier(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        num_leaves=31,
        random_state=42,
        n_jobs=-1,
    )

    tscv = TimeSeriesSplit(n_splits=5)
    scores = []
    for train_idx, val_idx in tscv.split(X_scaled):
        model.fit(X_scaled[train_idx], y.iloc[train_idx])
        score = model.score(X_scaled[val_idx], y.iloc[val_idx])
        scores.append(score)
        print(f"Fold accuracy: {score:.4f}")

    print(f"Mean accuracy: {np.mean(scores):.4f}")

    # 全データで最終学習
    model.fit(X_scaled, y)

    joblib.dump(model, f"{MODEL_DIR}/lgbm_model.pkl")
    joblib.dump(scaler, f"{MODEL_DIR}/scaler.pkl")
    print("Model saved.")


def train_incremental(df: pd.DataFrame):
    """逐次学習（直近データで追加学習）"""
    try:
        model = joblib.load(f"{MODEL_DIR}/lgbm_model.pkl")
        scaler = joblib.load(f"{MODEL_DIR}/scaler.pkl")
    except FileNotFoundError:
        print("No existing model found. Running full training instead.")
        train_full(df)
        return

    # 直近7日分のデータのみ使用
    recent = df[df["Date"] >= (pd.Timestamp.now() - pd.Timedelta(days=7)).strftime("%Y%m%d")]
    if len(recent) < 100:
        print("Not enough recent data for incremental training.")
        return

    X = recent[FEATURE_COLS].replace([np.inf, -np.inf], np.nan).dropna()
    y = recent.loc[X.index, "label"]
    mask = y != 0
    X, y = X[mask], y[mask]
    y = (y == 1).astype(int)

    X_scaled = scaler.transform(X)
    model.fit(X_scaled, y, init_model=model)

    joblib.dump(model, f"{MODEL_DIR}/lgbm_model.pkl")
    print("Incremental update done.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    df = load_features(engine)
    print(f"Loaded {len(df)} rows for training")

    if args.mode == "full":
        train_full(df)
    else:
        train_incremental(df)


if __name__ == "__main__":
    main()
