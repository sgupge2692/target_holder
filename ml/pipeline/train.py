"""
モデル学習スクリプト
--mode full        : フル再学習（週次）
--mode incremental : 逐次学習（日次）
--mode tune        : Optuna ハイパーパラメータ最適化 → フル再学習
--mode ensemble    : LightGBM + XGBoost スタッキングアンサンブル

v3 改善:
  - セクター・市場相対特徴量 / カレンダー特徴量を FEATURE_COLS に追加
  - LightGBM + XGBoost の weighted アンサンブル（--mode ensemble）
  - Optuna に pruning 追加（MedianPruner）
  - predict.py 向けに ensemble_weights.pkl を保存
"""
import os
import json
import argparse
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier, early_stopping, log_evaluation
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_DIR = "/app/models"
os.makedirs(MODEL_DIR, exist_ok=True)

# ── 特徴量リスト（feature_engineering.py と同期） ────────────────
FEATURE_COLS = [
    # テクニカル
    "ma5_deviation", "ma25_deviation", "ma75_deviation",
    "golden_cross", "dead_cross",
    "bb_percent_b", "bb_width",
    "rsi", "macd_diff",
    "volume_ratio", "price_up_vol_up",
    "body_ratio", "upper_shadow", "lower_shadow",
    # ラグリターン
    *[f"return_lag{i}" for i in range(1, 21)],
    # v2 追加
    "vwap_deviation", "atr_ratio", "obv_trend",
    "volume_momentum", "roc_5", "roc_20",
    "williams_r", "stoch_k", "stoch_d", "stoch_diff",
    # v3 追加: カレンダー
    "day_of_week", "is_monday", "is_friday",
    "month", "quarter", "is_month_end", "is_month_start",
    # v3 追加: セクター・市場相対
    "market_relative_return", "market_relative_rsi",
    "sector_relative_return", "sector_relative_rsi", "sector_relative_ma5",
    # v4 追加: ニュースセンチメント（NEWS_SENTIMENT=true 時のみ有効）
    "news_sentiment", "news_pos_count", "news_neg_count", "news_article_count",
    # v5 追加: ギャップ・出来高急増・ボラティリティ・価格位置・ストリーク
    "gap_up", "gap_down", "gap",
    "volume_spike", "volume_spike_ratio",
    "volatility_5d", "volatility_20d",
    "dist_from_high_52w", "dist_from_low_52w", "price_position_52w",
    "streak_up", "streak_down",
    "new_high_20d", "new_low_20d", "new_high_60d", "new_low_60d",
]

DEFAULT_LGBM_PARAMS = dict(
    n_estimators=1000,
    learning_rate=0.05,
    max_depth=6,
    num_leaves=63,
    min_child_samples=30,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=1.0,
    random_state=42,
    n_jobs=-1,
)

DEFAULT_XGB_PARAMS = dict(
    n_estimators=1000,
    learning_rate=0.05,
    max_depth=5,
    min_child_weight=5,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=1.0,
    random_state=42,
    n_jobs=-1,
    eval_metric="auc",
    early_stopping_rounds=50,
    verbosity=0,
)


# ────────────────────────────────────────────────────────────────
# データ準備
# ────────────────────────────────────────────────────────────────

def load_features(engine) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM features", engine)


def prepare_data(df: pd.DataFrame):
    available = [c for c in FEATURE_COLS if c in df.columns]
    missing   = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"[WARN] 特徴量 {len(missing)} 件が DB に未存在（スキップ）: {missing[:5]}...")

    X = df[available].replace([np.inf, -np.inf], np.nan).dropna()
    y = df.loc[X.index, "label"]

    mask = y != 0
    X, y = X[mask], y[mask]
    y = (y == 1).astype(int)

    pos = y.mean()
    neg = 1 - pos
    print(f"  UP: {pos:.1%}  DOWN: {neg:.1%}  total: {len(y)}")
    scale_pos_weight = neg / pos if pos > 0 else 1.0

    return X, y, scale_pos_weight, available


# ────────────────────────────────────────────────────────────────
# フル学習 (LightGBM)
# ────────────────────────────────────────────────────────────────

def train_full(df: pd.DataFrame, params: dict = None):
    X, y, scale_pos_weight, feat_cols = prepare_data(df)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    if params is None:
        params = DEFAULT_LGBM_PARAMS.copy()
    params["scale_pos_weight"] = scale_pos_weight

    tscv = TimeSeriesSplit(n_splits=5)
    aucs = []
    for fold, (tr_idx, val_idx) in enumerate(tscv.split(X_scaled), 1):
        m = LGBMClassifier(**params)
        m.fit(
            X_scaled[tr_idx], y.iloc[tr_idx],
            eval_set=[(X_scaled[val_idx], y.iloc[val_idx])],
            callbacks=[early_stopping(50, verbose=False), log_evaluation(-1)],
        )
        auc = roc_auc_score(y.iloc[val_idx], m.predict_proba(X_scaled[val_idx])[:, 1])
        aucs.append(auc)
        print(f"  Fold {fold} AUC: {auc:.4f}")

    print(f"  Mean AUC: {np.mean(aucs):.4f} ± {np.std(aucs):.4f}")

    model = LGBMClassifier(**params)
    model.fit(X_scaled, y, callbacks=[log_evaluation(-1)])

    joblib.dump(model,  f"{MODEL_DIR}/lgbm_model.pkl")
    joblib.dump(scaler, f"{MODEL_DIR}/scaler.pkl")
    joblib.dump(feat_cols, f"{MODEL_DIR}/feature_cols.pkl")
    joblib.dump({"mean_auc": float(np.mean(aucs)), "std_auc": float(np.std(aucs))},
                f"{MODEL_DIR}/metrics.pkl")
    print("LightGBM model saved.")
    return float(np.mean(aucs))


# ────────────────────────────────────────────────────────────────
# アンサンブル (LightGBM + XGBoost)
# ────────────────────────────────────────────────────────────────

def train_ensemble(df: pd.DataFrame):
    try:
        from xgboost import XGBClassifier
    except ImportError:
        print("[WARN] xgboost が未インストール。pip install xgboost でインストールしてください。")
        print("       LightGBM 単体でフル学習します。")
        train_full(df)
        return

    X, y, scale_pos_weight, feat_cols = prepare_data(df)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    tscv = TimeSeriesSplit(n_splits=5)
    lgbm_aucs, xgb_aucs, ens_aucs = [], [], []

    print("=== アンサンブル CV ===")
    for fold, (tr_idx, val_idx) in enumerate(tscv.split(X_scaled), 1):
        X_tr, X_val = X_scaled[tr_idx], X_scaled[val_idx]
        y_tr, y_val = y.iloc[tr_idx],   y.iloc[val_idx]

        # LightGBM
        lgbm = LGBMClassifier(**{**DEFAULT_LGBM_PARAMS, "scale_pos_weight": scale_pos_weight})
        lgbm.fit(X_tr, y_tr,
                 eval_set=[(X_val, y_val)],
                 callbacks=[early_stopping(50, verbose=False), log_evaluation(-1)])
        lgbm_prob = lgbm.predict_proba(X_val)[:, 1]
        lgbm_auc  = roc_auc_score(y_val, lgbm_prob)

        # XGBoost
        xgb_p = DEFAULT_XGB_PARAMS.copy()
        xgb_p["scale_pos_weight"] = scale_pos_weight
        xgb = XGBClassifier(**xgb_p)
        xgb.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
        xgb_prob = xgb.predict_proba(X_val)[:, 1]
        xgb_auc  = roc_auc_score(y_val, xgb_prob)

        # 重み付き平均（AUCが高い方を重く）
        w_lgbm = lgbm_auc / (lgbm_auc + xgb_auc)
        w_xgb  = xgb_auc  / (lgbm_auc + xgb_auc)
        ens_prob = w_lgbm * lgbm_prob + w_xgb * xgb_prob
        ens_auc  = roc_auc_score(y_val, ens_prob)

        lgbm_aucs.append(lgbm_auc)
        xgb_aucs.append(xgb_auc)
        ens_aucs.append(ens_auc)
        print(f"  Fold {fold}  LGBM: {lgbm_auc:.4f}  XGB: {xgb_auc:.4f}  Ensemble: {ens_auc:.4f}")

    print(f"  Mean AUC — LGBM: {np.mean(lgbm_aucs):.4f}  XGB: {np.mean(xgb_aucs):.4f}  Ensemble: {np.mean(ens_aucs):.4f}")

    # 全データで最終学習
    final_lgbm = LGBMClassifier(**{**DEFAULT_LGBM_PARAMS, "scale_pos_weight": scale_pos_weight})
    final_lgbm.fit(X_scaled, y, callbacks=[log_evaluation(-1)])

    xgb_p = DEFAULT_XGB_PARAMS.copy()
    xgb_p.pop("early_stopping_rounds", None)  # 全データ学習時は不要
    xgb_p["scale_pos_weight"] = scale_pos_weight
    final_xgb = XGBClassifier(**xgb_p)
    final_xgb.fit(X_scaled, y, verbose=False)

    # CV の平均 AUC を重みに
    mean_lgbm = np.mean(lgbm_aucs)
    mean_xgb  = np.mean(xgb_aucs)
    w_lgbm = mean_lgbm / (mean_lgbm + mean_xgb)
    w_xgb  = mean_xgb  / (mean_lgbm + mean_xgb)

    joblib.dump(final_lgbm, f"{MODEL_DIR}/lgbm_model.pkl")
    joblib.dump(final_xgb,  f"{MODEL_DIR}/xgb_model.pkl")
    joblib.dump(scaler,     f"{MODEL_DIR}/scaler.pkl")
    joblib.dump(feat_cols,  f"{MODEL_DIR}/feature_cols.pkl")
    joblib.dump({"lgbm": float(w_lgbm), "xgb": float(w_xgb)},
                f"{MODEL_DIR}/ensemble_weights.pkl")
    joblib.dump({"lgbm_auc": float(mean_lgbm), "xgb_auc": float(mean_xgb),
                 "ensemble_auc": float(np.mean(ens_aucs))},
                f"{MODEL_DIR}/metrics.pkl")
    print(f"Ensemble saved. Weights — LGBM: {w_lgbm:.3f}  XGB: {w_xgb:.3f}")


# ────────────────────────────────────────────────────────────────
# 逐次学習
# ────────────────────────────────────────────────────────────────

def train_incremental(df: pd.DataFrame):
    try:
        model  = joblib.load(f"{MODEL_DIR}/lgbm_model.pkl")
        scaler = joblib.load(f"{MODEL_DIR}/scaler.pkl")
    except FileNotFoundError:
        print("No existing model found. Running full training instead.")
        train_full(df)
        return

    recent = df[df["Date"] >= (pd.Timestamp.now() - pd.Timedelta(days=7)).strftime("%Y%m%d")]
    if len(recent) < 100:
        print("Not enough recent data for incremental training.")
        return

    feat_cols = joblib.load(f"{MODEL_DIR}/feature_cols.pkl") \
        if os.path.exists(f"{MODEL_DIR}/feature_cols.pkl") else FEATURE_COLS
    available = [c for c in feat_cols if c in recent.columns]

    X = recent[available].replace([np.inf, -np.inf], np.nan).dropna()
    y = recent.loc[X.index, "label"]
    mask = y != 0
    X, y = X[mask], y[mask]
    y = (y == 1).astype(int)

    X_scaled = scaler.transform(X)
    model.fit(X_scaled, y, init_model=model)
    joblib.dump(model, f"{MODEL_DIR}/lgbm_model.pkl")
    print("Incremental update done.")


# ────────────────────────────────────────────────────────────────
# Optuna チューニング
# ────────────────────────────────────────────────────────────────

def tune_and_train(df: pd.DataFrame):
    try:
        import optuna
        from optuna.pruners import MedianPruner
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        print("[WARN] optuna が未インストール。デフォルトパラメータでフル学習します。")
        train_full(df)
        return

    X, y, scale_pos_weight, feat_cols = prepare_data(df)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    tscv = TimeSeriesSplit(n_splits=3)

    def objective(trial):
        params = dict(
            n_estimators     = trial.suggest_int("n_estimators", 300, 1500),
            learning_rate    = trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            max_depth        = trial.suggest_int("max_depth", 4, 8),
            num_leaves       = trial.suggest_int("num_leaves", 15, 127),
            min_child_samples= trial.suggest_int("min_child_samples", 10, 50),
            subsample        = trial.suggest_float("subsample", 0.6, 1.0),
            colsample_bytree = trial.suggest_float("colsample_bytree", 0.6, 1.0),
            reg_alpha        = trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
            reg_lambda       = trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
            scale_pos_weight = scale_pos_weight,
            random_state     = 42,
            n_jobs           = -1,
        )
        aucs = []
        for step, (tr_idx, val_idx) in enumerate(tscv.split(X_scaled)):
            m = LGBMClassifier(**params)
            m.fit(
                X_scaled[tr_idx], y.iloc[tr_idx],
                eval_set=[(X_scaled[val_idx], y.iloc[val_idx])],
                callbacks=[early_stopping(30, verbose=False), log_evaluation(-1)],
            )
            auc = roc_auc_score(y.iloc[val_idx], m.predict_proba(X_scaled[val_idx])[:, 1])
            aucs.append(auc)
            trial.report(np.mean(aucs), step)
            if trial.should_prune():
                raise optuna.TrialPruned()
        return np.mean(aucs)

    print("Optuna チューニング開始（50 trials）...")
    study = optuna.create_study(direction="maximize", pruner=MedianPruner(n_warmup_steps=5))
    study.optimize(objective, n_trials=50, show_progress_bar=True)

    best_params = {**DEFAULT_LGBM_PARAMS, **study.best_params}
    print(f"\nBest AUC: {study.best_value:.4f}")
    joblib.dump(best_params, f"{MODEL_DIR}/best_params.pkl")
    train_full(df, params=best_params)


# ────────────────────────────────────────────────────────────────
# エントリポイント
# ────────────────────────────────────────────────────────────────

# ────────────────────────────────────────────────────────────────
# メトリクスをDBに保存
# ────────────────────────────────────────────────────────────────

def save_metrics_to_db(engine, mode: str, metrics: dict, n_samples: int, model=None, feat_cols=None):
    """学習後のメトリクスをmodel_metricsテーブルに保存"""
    try:
        # 特徴量重要度
        fi_json = None
        if model is not None and feat_cols is not None and hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
            fi_dict = dict(sorted(
                zip(feat_cols, importances.tolist()),
                key=lambda x: x[1], reverse=True
            )[:50])  # 上位50件
            fi_json = json.dumps(fi_dict, ensure_ascii=False)

        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO model_metrics
                    (trained_at, mode, mean_auc, std_auc, lgbm_auc, xgb_auc,
                     ensemble_auc, n_samples, feature_importances)
                VALUES
                    (:trained_at, :mode, :mean_auc, :std_auc, :lgbm_auc, :xgb_auc,
                     :ensemble_auc, :n_samples, :feature_importances)
            """), {
                "trained_at": datetime.now(timezone.utc),
                "mode": mode,
                "mean_auc": metrics.get("mean_auc"),
                "std_auc": metrics.get("std_auc"),
                "lgbm_auc": metrics.get("lgbm_auc"),
                "xgb_auc": metrics.get("xgb_auc"),
                "ensemble_auc": metrics.get("ensemble_auc"),
                "n_samples": n_samples,
                "feature_importances": fi_json,
            })
            conn.commit()
        print(f"[DB] model_metrics saved (mode={mode})")
    except Exception as e:
        print(f"[WARN] Failed to save metrics to DB: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode",
                        choices=["full", "incremental", "tune", "ensemble"],
                        default="incremental")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    df = load_features(engine)
    print(f"Loaded {len(df)} rows for training")

    if args.mode == "full":
        params = None
        bp = f"{MODEL_DIR}/best_params.pkl"
        if os.path.exists(bp):
            params = joblib.load(bp)
            print("best_params.pkl を使用します。")
        auc = train_full(df, params=params)
        # フルモデルのメトリクスを保存
        model = joblib.load(f"{MODEL_DIR}/lgbm_model.pkl")
        feat_cols = joblib.load(f"{MODEL_DIR}/feature_cols.pkl")
        metrics_data = joblib.load(f"{MODEL_DIR}/metrics.pkl")
        save_metrics_to_db(engine, "full", metrics_data, len(df), model, feat_cols)
    elif args.mode == "tune":
        tune_and_train(df)
        # tune後はfull学習と同じメトリクスが保存されている
        if os.path.exists(f"{MODEL_DIR}/metrics.pkl"):
            model = joblib.load(f"{MODEL_DIR}/lgbm_model.pkl")
            feat_cols = joblib.load(f"{MODEL_DIR}/feature_cols.pkl")
            metrics_data = joblib.load(f"{MODEL_DIR}/metrics.pkl")
            save_metrics_to_db(engine, "tune", metrics_data, len(df), model, feat_cols)
    elif args.mode == "ensemble":
        train_ensemble(df)
        if os.path.exists(f"{MODEL_DIR}/metrics.pkl"):
            model = joblib.load(f"{MODEL_DIR}/lgbm_model.pkl")
            feat_cols = joblib.load(f"{MODEL_DIR}/feature_cols.pkl")
            metrics_data = joblib.load(f"{MODEL_DIR}/metrics.pkl")
            save_metrics_to_db(engine, "ensemble", metrics_data, len(df), model, feat_cols)
    else:
        train_incremental(df)


if __name__ == "__main__":
    main()
