"""
モデル学習スクリプト
--mode full:        フル再学習（週次）
--mode incremental: 逐次学習（日次差分）
"""
import os
import argparse
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report
from lightgbm import LGBMClassifier
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_DIR = os.getenv("MODEL_DIR", "/app/models")
os.makedirs(MODEL_DIR, exist_ok=True)

# feature_engineering.py と同一定義
FEATURE_COLS = [
    "ma5_deviation", "ma25_deviation", "ma75_deviation",
    "golden_cross", "dead_cross",
    "bb_percent_b", "bb_width",
    "rsi", "macd_diff",
    "volume_ratio", "price_up_vol_up",
    "body_ratio", "upper_shadow", "lower_shadow",
] + [f"ret_lag_{i}" for i in range(1, 21)]


def load_features(engine) -> pd.DataFrame:
    return pd.read_sql(text("SELECT * FROM features ORDER BY date"), engine)


def prepare_xy(df: pd.DataFrame):
    """学習用のX, yを作成（中立ラベル0は除外）"""
    X = df[FEATURE_COLS].replace([np.inf, -np.inf], np.nan)
    y = df["label"]
    mask = (y != 0) & X.notna().all(axis=1)
    X = X[mask]
    y = (y[mask] == 1).astype(int)  # 1: 上昇, 0: 下落
    return X, y


def train_full(df: pd.DataFrame):
    """フル再学習: TimeSeriesSplitで検証後、全データで最終学習"""
    print("=== フル再学習モード ===")
    X, y = prepare_xy(df)
    print(f"  学習サンプル: {len(X)} (上昇: {y.sum()}, 下落: {(~y.astype(bool)).sum()})")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LGBMClassifier(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        num_leaves=31,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )

    # 時系列クロスバリデーション
    tscv = TimeSeriesSplit(n_splits=5)
    scores = []
    for fold, (train_idx, val_idx) in enumerate(tscv.split(X_scaled), 1):
        model.fit(X_scaled[train_idx], y.iloc[train_idx])
        preds = model.predict(X_scaled[val_idx])
        score = (preds == y.iloc[val_idx]).mean()
        scores.append(score)
        print(f"  Fold {fold} accuracy: {score:.4f}")

    print(f"  平均accuracy: {np.mean(scores):.4f} ± {np.std(scores):.4f}")

    # 全データで最終学習
    model.fit(X_scaled, y)

    # 特徴量重要度 Top10
    feat_imp = pd.Series(model.feature_importances_, index=FEATURE_COLS)
    print("\n  特徴量重要度 Top10:")
    for feat, imp in feat_imp.nlargest(10).items():
        print(f"    {feat}: {imp:.1f}")

    joblib.dump(model, f"{MODEL_DIR}/lgbm_model.pkl")
    joblib.dump(scaler, f"{MODEL_DIR}/scaler.pkl")
    print(f"\n  モデル保存: {MODEL_DIR}/")


def train_incremental(df: pd.DataFrame):
    """逐次学習: 既存モデルに直近データを追加学習"""
    print("=== 逐次学習モード ===")
    model_path  = f"{MODEL_DIR}/lgbm_model.pkl"
    scaler_path = f"{MODEL_DIR}/scaler.pkl"

    if not os.path.exists(model_path):
        print("  既存モデルがありません。フル再学習に切り替えます。")
        train_full(df)
        return

    model  = joblib.load(model_path)
    scaler = joblib.load(scaler_path)

    # 直近7日のデータのみ
    cutoff = (pd.Timestamp.now() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    recent = df[df["date"] >= cutoff]
    print(f"  直近7日のデータ: {len(recent)} 行")

    if len(recent) < 50:
        print("  データが少なすぎます。スキップします。")
        return

    X, y = prepare_xy(recent)
    if len(X) < 10:
        print("  有効サンプルが少なすぎます。スキップします。")
        return

    X_scaled = scaler.transform(X)
    # LightGBMのinit_model（継続学習）
    model.fit(X_scaled, y, init_model=model)

    joblib.dump(model, model_path)
    print(f"  逐次学習完了。{len(X)} サンプルで更新。")

    # 検証
    preds = model.predict(X_scaled)
    acc = (preds == y).mean()
    print(f"  直近データの accuracy: {acc:.4f}")
    print(classification_report(y, preds, target_names=["下落", "上昇"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental",
                        help="full: フル再学習, incremental: 直近差分学習")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    df = load_features(engine)
    print(f"特徴量データ読み込み: {len(df)} 行")

    if args.mode == "full":
        train_full(df)
    else:
        train_incremental(df)


if __name__ == "__main__":
    main()
