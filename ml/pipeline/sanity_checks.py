#!/usr/bin/env python3
"""
学習データの健全性チェック（実データで初めて学習するときに必ず実行する）

精度が「高く出すぎる」ときは、モデルが良いのではなく、特徴量にラベル（翌日の結果）が
漏れ込んでいる（リーク）可能性が高い。株価の翌日予測で本当に出る精度は、AUC 0.52〜0.55 程度が現実的。
それを大きく超えたら、まず疑う。

チェック内容:
  1. 単一特徴量スキャン : 1 つの特徴量だけで AUC が極端に高い（または低い）ものを洗い出す
  2. ラベルシャッフル   : 各日の中でラベルをランダムに入れ替えて学習。AUC が 0.5 付近に戻らなければ、
                          評価の仕組み自体にリークがある（日付分割・並び順・前処理の不具合など）

使い方:
  docker compose exec ml python pipeline/sanity_checks.py
  終了コード: 0=問題なし、1=疑わしい点あり
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

try:
    from pipeline.evaluation import walk_forward_splits, split_for_early_stopping
except ImportError:  # python pipeline/sanity_checks.py で直接実行する場合
    sys.path.insert(0, os.path.dirname(__file__))
    from evaluation import walk_forward_splits, split_for_early_stopping

# 1 つの特徴量だけでこの AUC を超える（または 1 - この値を下回る）ものは、リーク候補として警告する
SUSPECT_AUC = 0.60
# ラベルシャッフル後の AUC が 0.5 からこれ以上ずれたら、評価の仕組みにリークがあるとみなす
SHUFFLE_TOLERANCE = 0.02


def single_feature_auc_scan(X: pd.DataFrame, y: pd.Series, suspect_auc: float = SUSPECT_AUC) -> pd.DataFrame:
    """
    特徴量ごとに、その値そのものを予測スコアとみなしたときの AUC を返す。

    正常な特徴量（RSI、移動平均乖離など）の単独 AUC は 0.5 近辺。0.6 を超えるものは、
    翌日の値（next_return 由来、未来のデータを含む移動平均など）が混ざっていないかを疑う。
    """
    rows = []
    yv = y.values
    for col in X.columns:
        v = X[col].values
        if np.nanstd(v) == 0 or len(np.unique(yv)) < 2:
            continue
        try:
            auc = float(roc_auc_score(yv, v))
        except ValueError:
            continue
        rows.append({"feature": col, "auc": auc, "suspect": auc >= suspect_auc or auc <= 1 - suspect_auc})
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["feature", "auc", "suspect", "strength"])
    df["strength"] = (df["auc"] - 0.5).abs()
    return df.sort_values("strength", ascending=False).reset_index(drop=True)


def shuffle_labels_within_date(y: pd.Series, dates: pd.Series, seed: int = 0) -> pd.Series:
    """各日の中でラベルを入れ替える。日ごとの上昇・下落の比率（地合い）は保ったまま、銘柄との対応だけを壊す。"""
    rng = np.random.default_rng(seed)
    out = y.to_numpy(copy=True)
    d = pd.to_datetime(pd.Series(dates).astype(str)).values
    for day in np.unique(d):
        idx = np.flatnonzero(d == day)
        out[idx] = rng.permutation(out[idx])
    return pd.Series(out, index=y.index)


def shuffled_label_auc(
    X: pd.DataFrame,
    y: pd.Series,
    dates: pd.Series,
    n_splits: int = 4,
    embargo_days: int = 2,
    seed: int = 0,
    n_estimators: int = 60,
) -> float:
    """ラベルをシャッフルして日付ウォークフォワードで学習したときの平均 AUC（正しい仕組みなら 0.5 付近）。"""
    from lightgbm import LGBMClassifier

    y_shuf = shuffle_labels_within_date(y, dates, seed)
    Xv = X.values
    aucs = []
    for tr_idx, val_idx in walk_forward_splits(dates, n_splits, embargo_days):
        fit_idx, es_idx = split_for_early_stopping(tr_idx, dates, embargo_days=embargo_days)
        m = LGBMClassifier(n_estimators=n_estimators, learning_rate=0.05, num_leaves=15,
                           min_child_samples=50, random_state=seed, n_jobs=-1, verbose=-1)
        m.fit(Xv[fit_idx], y_shuf.iloc[fit_idx])
        prob = m.predict_proba(Xv[val_idx])[:, 1]
        if y_shuf.iloc[val_idx].nunique() == 2:
            aucs.append(roc_auc_score(y_shuf.iloc[val_idx], prob))
    return float(np.mean(aucs)) if aucs else float("nan")


def run_checks(X: pd.DataFrame, y: pd.Series, dates: pd.Series, verbose: bool = True) -> dict:
    """全チェックを実行して結果を返す。result['ok'] が False なら疑わしい点がある。"""
    scan = single_feature_auc_scan(X, y)
    suspects = scan[scan["suspect"]] if not scan.empty else scan
    shuffled = shuffled_label_auc(X, y, dates)
    shuffle_ok = bool(abs(shuffled - 0.5) <= SHUFFLE_TOLERANCE)

    if verbose:
        print("=== 1. 単一特徴量スキャン（上位10件 / 単独AUCが 0.5 から遠い順）===")
        for _, r in scan.head(10).iterrows():
            flag = "  ← リーク疑い" if r["suspect"] else ""
            print(f"  {r['feature']:<28} AUC {r['auc']:.4f}{flag}")
        print(f"  → 疑わしい特徴量: {len(suspects)} 件（基準: AUC ≥ {SUSPECT_AUC:.2f} または ≤ {1 - SUSPECT_AUC:.2f}）")
        print()
        print("=== 2. ラベルシャッフル（各日の中でラベルを入れ替えて学習）===")
        print(f"  平均 AUC {shuffled:.4f}（期待値 0.5 ± {SHUFFLE_TOLERANCE}）→ {'OK' if shuffle_ok else '要調査'}")
        print()

    ok = bool(suspects.empty and shuffle_ok)
    if verbose:
        if ok:
            print("結果: 問題なし。学習時の AUC がこの範囲なら、リークの可能性は低い。")
            print("      ただし 0.55 を大きく超える AUC が出たら、結果を信じる前に特徴量を見直すこと。")
        else:
            print("結果: 疑わしい点あり。特徴量の計算で「翌日以降の値」を使っていないか確認してください。")
    return {
        "ok": ok,
        "suspect_features": suspects["feature"].tolist() if not suspects.empty else [],
        "shuffled_auc": shuffled,
        "scan": scan,
    }


def main() -> int:
    from dotenv import load_dotenv
    from sqlalchemy import create_engine

    try:
        from pipeline.train import load_features, prepare_data_with_meta
    except ImportError:
        from train import load_features, prepare_data_with_meta

    load_dotenv()
    url = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
    if not url:
        print("DATABASE_URL が未設定です")
        return 1

    df = load_features(create_engine(url))
    X, y, _, _, meta = prepare_data_with_meta(df)
    result = run_checks(X, y, meta["Date"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
