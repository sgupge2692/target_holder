"""
ニュース特徴量の A/B 比較

「ニュースを足したら本当に良くなるのか」を、同じ行・同じ分割で測る。
  A: ニュース特徴量なし（テクニカルなど既存の特徴量のみ）
  B: ニュース特徴量あり
ニュースを観測できていた日（news_covered=1）の行だけで、日付ウォークフォワードCVを回して比べる。

  python pipeline/news_ablation.py

見方:
  - 差が小さい／符号がフォールドごとに揺れる → ニュースの効果は確認できない。採用しない
  - 日別IC の改善がフォールドをまたいで一貫して正 → 採用を検討（それでも蓄積期間が短いうちは慎重に）
  - 蓄積が短いと、検証期間が数十日になり偶然に左右される。差は「勝った/負けた」ではなく、ばらつきとセットで見る
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from evaluation import evaluate_predictions, split_for_early_stopping, walk_forward_splits
from news_store import COVERED_COL, NEWS_FEATURE_COLS

N_SPLITS = 4
EMBARGO_DAYS = 2
TOP_K = 20
CONFIDENCE = 0.60


def _fit_predict(X_fit, y_fit, X_es, y_es, X_val, seed: int = 42) -> np.ndarray:
    from lightgbm import LGBMClassifier, early_stopping, log_evaluation
    m = LGBMClassifier(
        n_estimators=500, learning_rate=0.05, num_leaves=31, min_child_samples=50,
        subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=seed, n_jobs=-1, verbose=-1,
    )
    m.fit(X_fit, y_fit, eval_set=[(X_es, y_es)], callbacks=[early_stopping(30, verbose=False), log_evaluation(-1)])
    return m.predict_proba(X_val)[:, 1]


def compare_feature_sets(
    df: pd.DataFrame,
    base_cols: list[str],
    extra_cols: list[str],
    target_col: str = "label_excess",
    return_col: str = "excess_return",
    n_splits: int = N_SPLITS,
    embargo_days: int = EMBARGO_DAYS,
    min_train_dates: int = 30,
) -> dict:
    """
    同じ行・同じ分割で、base_cols だけ（A）と base_cols+extra_cols（B）を比べる。

    Returns: {"folds": [{"fold","A","B"}...], "mean_A": {...}, "mean_B": {...}, "delta": {...}, "n_rows", "n_dates"}
    """
    df = df.sort_values(["Date", "Code"]).reset_index(drop=True)
    cols_b = base_cols + [c for c in extra_cols if c not in base_cols]
    use = df[cols_b + [target_col, "Date"] + ([return_col] if return_col in df.columns else [])]
    use = use.replace([np.inf, -np.inf], np.nan).dropna()
    use = use[use[target_col] != 0].reset_index(drop=True)
    y = (use[target_col] == 1).astype(int)
    ret = use[return_col].values if return_col in use.columns else np.full(len(use), np.nan)

    folds = []
    for fold, (tr, va) in enumerate(
        walk_forward_splits(use["Date"], n_splits, embargo_days, min_train_dates=min_train_dates), 1
    ):
        fit, es = split_for_early_stopping(tr, use["Date"], embargo_days=embargo_days)
        row = {"fold": fold}
        for name, cols in (("A", base_cols), ("B", cols_b)):
            X = use[cols].values
            prob = _fit_predict(X[fit], y.iloc[fit], X[es], y.iloc[es], X[va])
            row[name] = evaluate_predictions(use["Date"].iloc[va], y.iloc[va].values, prob, ret[va], TOP_K, CONFIDENCE)
        folds.append(row)

    keys = ["auc", "daily_auc", "daily_ic", "precision_topk"]
    mean = lambda arm, k: float(np.nanmean([f[arm][k] for f in folds])) if folds else float("nan")
    mean_a = {k: mean("A", k) for k in keys}
    mean_b = {k: mean("B", k) for k in keys}
    return {
        "folds": folds, "mean_A": mean_a, "mean_B": mean_b,
        "delta": {k: mean_b[k] - mean_a[k] for k in keys},
        "n_rows": len(use), "n_dates": int(use["Date"].nunique()),
    }


def main() -> int:
    from sqlalchemy import create_engine
    from train import FEATURE_COLS, load_features

    df = load_features(create_engine(os.environ["DATABASE_URL"]))
    if COVERED_COL not in df.columns or df[COVERED_COL].sum() == 0:
        print("ニュースを観測できた日がありません。collect_news.py を毎日回して蓄積してください。")
        return 1
    covered = df[df[COVERED_COL] == 1]
    print(f"ニュース観測 {covered['Date'].nunique()} 日 / {len(covered)} 行で比較します。")
    res = compare_feature_sets(covered, [c for c in FEATURE_COLS if c in covered.columns], NEWS_FEATURE_COLS)
    if not res["folds"]:
        print("期間が短く、検証フォールドを作れません。もう少し蓄積してください。")
        return 1

    print(f"\n{'':<10}{'AUC':>9}{'日別AUC':>10}{'日別IC':>10}{'上位'+str(TOP_K)+'的中':>12}")
    for label, m in (("A 既存のみ", res["mean_A"]), ("B +ニュース", res["mean_B"]), ("差 B-A", res["delta"])):
        print(f"{label:<10}{m['auc']:>9.4f}{m['daily_auc']:>10.4f}{m['daily_ic']:>+10.4f}{m['precision_topk']:>12.3f}")
    print("\nフォールドごとの日別IC（B-A）:",
          " ".join(f"{f['B']['daily_ic'] - f['A']['daily_ic']:+.4f}" for f in res["folds"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
