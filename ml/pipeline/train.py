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
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier, early_stopping, log_evaluation
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

try:
    from pipeline.evaluation import walk_forward_splits, split_for_early_stopping, evaluate_predictions
except ImportError:  # python pipeline/train.py で直接実行する場合
    from evaluation import walk_forward_splits, split_for_early_stopping, evaluate_predictions

DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_DIR = os.getenv("MODEL_DIR", "/app/models")

# 評価設定
N_SPLITS = 5          # ウォークフォワードの分割数
EMBARGO_DAYS = 2      # 学習と検証の間を空ける営業日数
TOP_K = 20            # 「毎日、上位K銘柄」の的中率を測る
CONFIDENCE = 0.60     # predict.py の CONFIDENCE_THRESHOLD と揃える

# 目的変数: 市場平均に対する超過リターン（feature_engineering.add_excess_labels）。
# features に無い（旧データ）場合は従来の絶対リターンのラベルにフォールバックする。
TARGET_COL = "label_excess"
FALLBACK_TARGET_COL = "label"
RETURN_COL = "excess_return"
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
    return pd.read_sql('SELECT * FROM features ORDER BY "Date", "Code"', engine)


def prepare_data_with_meta(df: pd.DataFrame):
    """
    学習用データを作る。日付順に並べ替え、評価に必要な日付・翌日リターンも返す。

    Returns:
        X, y, scale_pos_weight, feature_cols, meta(DataFrame: Date, next_return)
        いずれも行の並びは同一（日付 → 銘柄コード順、index は 0..n-1）
    """
    df = df.sort_values(["Date", "Code"]).reset_index(drop=True)

    available = [c for c in FEATURE_COLS if c in df.columns]
    missing   = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"[WARN] 特徴量 {len(missing)} 件が DB に未存在（スキップ）: {missing[:5]}...")

    target_col = TARGET_COL if TARGET_COL in df.columns else FALLBACK_TARGET_COL
    return_col = RETURN_COL if target_col == TARGET_COL and RETURN_COL in df.columns else "next_return"
    print(f"  目的変数: {target_col}（IC は {return_col} で評価）")

    X = df[available].replace([np.inf, -np.inf], np.nan).dropna()
    y = df.loc[X.index, target_col]

    mask = y != 0
    X, y = X[mask], y[mask]
    y = (y == 1).astype(int)

    meta = pd.DataFrame({
        "Date": df.loc[X.index, "Date"],
        "next_return": df.loc[X.index, return_col] if return_col in df.columns else np.nan,
    })

    X = X.reset_index(drop=True)
    y = y.reset_index(drop=True)
    meta = meta.reset_index(drop=True)

    pos = y.mean()
    neg = 1 - pos
    print(f"  UP: {pos:.1%}  DOWN: {neg:.1%}  total: {len(y)}")
    scale_pos_weight = neg / pos if pos > 0 else 1.0

    return X, y, scale_pos_weight, available, meta


def prepare_data(df: pd.DataFrame):
    X, y, spw, cols, _ = prepare_data_with_meta(df)
    return X, y, spw, cols


def _print_eval(label: str, m: dict):
    print(f"    {label:<9} AUC {m['auc']:.4f} | 日別AUC {m['daily_auc']:.4f} | IC {m['daily_ic']:+.4f} | "
          f"上位{TOP_K}的中 {m['precision_topk']:.3f} | 確度{CONFIDENCE:.0%}以上 的中 {m['hit_rate_conf']:.3f} "
          f"(出現率 {m['coverage_conf']:.1%})")


def _mean_metric(rows: list, key: str) -> float:
    return float(np.nanmean([r[key] for r in rows]))


# ────────────────────────────────────────────────────────────────
# フル学習 (LightGBM)
# ────────────────────────────────────────────────────────────────

def train_full(df: pd.DataFrame, params: dict = None):
    X, y, scale_pos_weight, feat_cols, meta = prepare_data_with_meta(df)

    if params is None:
        params = DEFAULT_LGBM_PARAMS.copy()
    params = {**params, "scale_pos_weight": scale_pos_weight}

    # 木モデルはスケール不変なので CV は生の特徴量で行う（scaler は predict.py 互換のため保存のみ）
    Xv = X.values
    folds, best_iters = [], []
    print("=== LightGBM ウォークフォワードCV（日付分割・embargo付き）===")
    for fold, (tr_idx, val_idx) in enumerate(walk_forward_splits(meta["Date"], N_SPLITS, EMBARGO_DAYS), 1):
        fit_idx, es_idx = split_for_early_stopping(tr_idx, meta["Date"], embargo_days=EMBARGO_DAYS)
        m = LGBMClassifier(**params)
        m.fit(
            Xv[fit_idx], y.iloc[fit_idx],
            eval_set=[(Xv[es_idx], y.iloc[es_idx])],      # early stopping は学習側の末尾だけで行う
            callbacks=[early_stopping(50, verbose=False), log_evaluation(-1)],
        )
        prob = m.predict_proba(Xv[val_idx])[:, 1]
        res = evaluate_predictions(
            meta["Date"].iloc[val_idx], y.iloc[val_idx].values, prob,
            meta["next_return"].iloc[val_idx].values, TOP_K, CONFIDENCE,
        )
        folds.append(res)
        best_iters.append(m.best_iteration_ or params["n_estimators"])
        print(f"  Fold {fold} (train {len(tr_idx)} / val {len(val_idx)}, best_iter {best_iters[-1]})")
        _print_eval("LGBM", res)

    mean_auc = _mean_metric(folds, "auc")
    std_auc = float(np.nanstd([r["auc"] for r in folds]))
    print(f"  Mean AUC: {mean_auc:.4f} ± {std_auc:.4f}  /  日別AUC {_mean_metric(folds, 'daily_auc'):.4f}  "
          f"/  IC {_mean_metric(folds, 'daily_ic'):+.4f}")

    # 最終モデル: CV で見つけた木の本数に固定（全データを 1000 本で学習すると過学習する）
    final_params = {**params, "n_estimators": max(int(np.mean(best_iters) * 1.1), 50)}
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = LGBMClassifier(**final_params)
    model.fit(X_scaled, y, callbacks=[log_evaluation(-1)])

    joblib.dump(model,  f"{MODEL_DIR}/lgbm_model.pkl")
    joblib.dump(scaler, f"{MODEL_DIR}/scaler.pkl")
    joblib.dump(feat_cols, f"{MODEL_DIR}/feature_cols.pkl")
    joblib.dump({
        "mean_auc": mean_auc, "std_auc": std_auc,
        "daily_auc": _mean_metric(folds, "daily_auc"),
        "daily_ic": _mean_metric(folds, "daily_ic"),
        "precision_topk": _mean_metric(folds, "precision_topk"),
        "hit_rate_conf": _mean_metric(folds, "hit_rate_conf"),
    }, f"{MODEL_DIR}/metrics.pkl")
    print("LightGBM model saved.")
    return mean_auc


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

    X, y, scale_pos_weight, feat_cols, meta = prepare_data_with_meta(df)
    Xv = X.values

    lgbm_rows, xgb_rows, ens_rows = [], [], []
    lgbm_iters, xgb_iters = [], []

    print("=== アンサンブル ウォークフォワードCV（日付分割・embargo付き）===")
    for fold, (tr_idx, val_idx) in enumerate(walk_forward_splits(meta["Date"], N_SPLITS, EMBARGO_DAYS), 1):
        fit_idx, es_idx = split_for_early_stopping(tr_idx, meta["Date"], embargo_days=EMBARGO_DAYS)
        dates_val = meta["Date"].iloc[val_idx]
        ret_val = meta["next_return"].iloc[val_idx].values
        y_val = y.iloc[val_idx].values

        lgbm = LGBMClassifier(**{**DEFAULT_LGBM_PARAMS, "scale_pos_weight": scale_pos_weight})
        lgbm.fit(Xv[fit_idx], y.iloc[fit_idx],
                 eval_set=[(Xv[es_idx], y.iloc[es_idx])],
                 callbacks=[early_stopping(50, verbose=False), log_evaluation(-1)])
        lgbm_prob = lgbm.predict_proba(Xv[val_idx])[:, 1]

        xgb_p = DEFAULT_XGB_PARAMS.copy()
        xgb_p["scale_pos_weight"] = scale_pos_weight
        xgb = XGBClassifier(**xgb_p)
        xgb.fit(Xv[fit_idx], y.iloc[fit_idx], eval_set=[(Xv[es_idx], y.iloc[es_idx])], verbose=False)
        xgb_prob = xgb.predict_proba(Xv[val_idx])[:, 1]

        lgbm_res = evaluate_predictions(dates_val, y_val, lgbm_prob, ret_val, TOP_K, CONFIDENCE)
        xgb_res  = evaluate_predictions(dates_val, y_val, xgb_prob,  ret_val, TOP_K, CONFIDENCE)

        # 重みは「検証フォールドの AUC」ではなく固定の等重みで開始し、
        # 学習側の情報だけで決める（検証期間の結果で重みを決めると評価が楽観的になる）
        ens_prob = 0.5 * lgbm_prob + 0.5 * xgb_prob
        ens_res = evaluate_predictions(dates_val, y_val, ens_prob, ret_val, TOP_K, CONFIDENCE)

        lgbm_rows.append(lgbm_res); xgb_rows.append(xgb_res); ens_rows.append(ens_res)
        lgbm_iters.append(lgbm.best_iteration_ or DEFAULT_LGBM_PARAMS["n_estimators"])
        xgb_iters.append((getattr(xgb, "best_iteration", None) or DEFAULT_XGB_PARAMS["n_estimators"]) + 1)

        print(f"  Fold {fold} (train {len(tr_idx)} / val {len(val_idx)})")
        _print_eval("LGBM", lgbm_res)
        _print_eval("XGB", xgb_res)
        _print_eval("Ensemble", ens_res)

    mean_lgbm = _mean_metric(lgbm_rows, "auc")
    mean_xgb  = _mean_metric(xgb_rows, "auc")
    mean_ens  = _mean_metric(ens_rows, "auc")
    print(f"  Mean AUC — LGBM: {mean_lgbm:.4f}  XGB: {mean_xgb:.4f}  Ensemble: {mean_ens:.4f}")
    print(f"  Ensemble 日別AUC {_mean_metric(ens_rows, 'daily_auc'):.4f} / IC {_mean_metric(ens_rows, 'daily_ic'):+.4f} "
          f"/ 上位{TOP_K}的中 {_mean_metric(ens_rows, 'precision_topk'):.3f}")

    # 最終モデル: CV で見つけた木の本数に固定して全データで学習
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    final_lgbm = LGBMClassifier(**{
        **DEFAULT_LGBM_PARAMS, "scale_pos_weight": scale_pos_weight,
        "n_estimators": max(int(np.mean(lgbm_iters) * 1.1), 50),
    })
    final_lgbm.fit(X_scaled, y, callbacks=[log_evaluation(-1)])

    xgb_p = DEFAULT_XGB_PARAMS.copy()
    xgb_p.pop("early_stopping_rounds", None)
    xgb_p["scale_pos_weight"] = scale_pos_weight
    xgb_p["n_estimators"] = max(int(np.mean(xgb_iters) * 1.1), 50)
    final_xgb = XGBClassifier(**xgb_p)
    final_xgb.fit(X_scaled, y, verbose=False)

    # predict.py 互換のため重みは保存する（現状は等重み）
    w_lgbm, w_xgb = 0.5, 0.5

    joblib.dump(final_lgbm, f"{MODEL_DIR}/lgbm_model.pkl")
    joblib.dump(final_xgb,  f"{MODEL_DIR}/xgb_model.pkl")
    joblib.dump(scaler,     f"{MODEL_DIR}/scaler.pkl")
    joblib.dump(feat_cols,  f"{MODEL_DIR}/feature_cols.pkl")
    joblib.dump({"lgbm": w_lgbm, "xgb": w_xgb}, f"{MODEL_DIR}/ensemble_weights.pkl")
    joblib.dump({
        "lgbm_auc": mean_lgbm, "xgb_auc": mean_xgb, "ensemble_auc": mean_ens,
        "daily_auc": _mean_metric(ens_rows, "daily_auc"),
        "daily_ic": _mean_metric(ens_rows, "daily_ic"),
        "precision_topk": _mean_metric(ens_rows, "precision_topk"),
        "hit_rate_conf": _mean_metric(ens_rows, "hit_rate_conf"),
    }, f"{MODEL_DIR}/metrics.pkl")
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

    target_col = TARGET_COL if TARGET_COL in recent.columns else FALLBACK_TARGET_COL
    X = recent[available].replace([np.inf, -np.inf], np.nan).dropna()
    y = recent.loc[X.index, target_col]
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

    X, y, scale_pos_weight, feat_cols, meta = prepare_data_with_meta(df)
    Xv = X.values
    splits = list(walk_forward_splits(meta["Date"], 3, EMBARGO_DAYS))

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
        for step, (tr_idx, val_idx) in enumerate(splits):
            fit_idx, es_idx = split_for_early_stopping(tr_idx, meta["Date"], embargo_days=EMBARGO_DAYS)
            m = LGBMClassifier(**params)
            m.fit(
                Xv[fit_idx], y.iloc[fit_idx],
                eval_set=[(Xv[es_idx], y.iloc[es_idx])],
                callbacks=[early_stopping(30, verbose=False), log_evaluation(-1)],
            )
            auc = roc_auc_score(y.iloc[val_idx], m.predict_proba(Xv[val_idx])[:, 1])
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
