"""
モデル評価ユーティリティ

株価の「銘柄 × 日付」パネルデータを正しく評価するための部品。

従来の TimeSeriesSplit は行の並び順で分割していたが、特徴量テーブルは
銘柄コード順に並んでいるため、「時間」ではなく「銘柄コード」で分割されていた。
その結果、同じ日の別銘柄が学習側と検証側に混在し（市場全体の値動きが漏れる）、
AUC が実力より高く出る。ここでは日付ベースのウォークフォワードで分割する。
"""
from __future__ import annotations

from typing import Iterator, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


def walk_forward_splits(
    dates: pd.Series,
    n_splits: int = 5,
    embargo_days: int = 2,
    min_train_dates: int = 60,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """
    日付ベースの拡張ウィンドウ分割。

    - 検証期間は日付軸を n_splits+1 個のブロックに分けた後ろ n_splits 個
    - 学習は検証ブロックの開始より embargo_days 営業日以上前の日付だけを使う
      （ラベルが翌日リターンなので、直前日を学習に入れると検証期間に漏れる）
    - 返すのは行の位置インデックス（positional）

    Yields:
        (train_idx, val_idx)
    """
    d = pd.to_datetime(dates.astype(str)).reset_index(drop=True)
    unique_dates = np.sort(d.unique())
    n_dates = len(unique_dates)
    if n_dates < min_train_dates + n_splits:
        raise ValueError(
            f"日付数が足りません: {n_dates} 日（最低 {min_train_dates + n_splits} 日必要）"
        )

    block = n_dates // (n_splits + 1)
    d_values = d.values

    for k in range(1, n_splits + 1):
        val_start = k * block
        val_end = n_dates if k == n_splits else (k + 1) * block
        train_end = val_start - embargo_days          # この日付「未満」を学習に使う
        if train_end < min_train_dates:
            continue

        train_mask = d_values < unique_dates[train_end]
        val_mask = d_values >= unique_dates[val_start]
        if val_end < n_dates:
            val_mask &= d_values < unique_dates[val_end]

        yield np.flatnonzero(train_mask), np.flatnonzero(val_mask)


def split_for_early_stopping(
    train_idx: np.ndarray,
    dates: pd.Series,
    holdout_ratio: float = 0.1,
    embargo_days: int = 2,
) -> tuple[np.ndarray, np.ndarray]:
    """
    学習データの末尾の日付を early stopping 専用に切り出す。

    検証フォールド自体を early stopping に使うと、報告する AUC が楽観的になる。
    """
    d = pd.to_datetime(dates.astype(str)).reset_index(drop=True).values[train_idx]
    unique_dates = np.sort(np.unique(d))
    n = len(unique_dates)
    es_start = unique_dates[int(n * (1 - holdout_ratio))]
    fit_end_pos = max(int(n * (1 - holdout_ratio)) - embargo_days, 1)
    fit_end = unique_dates[fit_end_pos]

    fit_idx = train_idx[d < fit_end]
    es_idx = train_idx[d >= es_start]
    return fit_idx, es_idx


def evaluate_predictions(
    dates: pd.Series,
    y_true: np.ndarray,
    prob_up: np.ndarray,
    next_return: Optional[np.ndarray] = None,
    top_k: int = 20,
    confidence: float = 0.60,
) -> dict:
    """
    サービスの使われ方（毎日、確度の高い数銘柄を見る）に合わせた指標を返す。

    - auc            : 全体の AUC（参考値）
    - daily_auc      : 日ごとの AUC の平均（日付ごとの銘柄の並び替え性能）
    - daily_ic       : 日ごとの 予測確率 と 翌日リターン の Spearman 相関の平均
    - precision_topk : 各日の上昇確率 上位 top_k 銘柄のうち実際に上昇した割合
    - hit_rate_conf  : 確率が confidence 以上（または 1-confidence 以下）の銘柄の的中率
    - coverage_conf  : 上記に該当した割合（出すシグナルの量）
    """
    df = pd.DataFrame({
        "date": pd.to_datetime(pd.Series(dates).astype(str)).values,
        "y": np.asarray(y_true),
        "p": np.asarray(prob_up),
    })
    if next_return is not None:
        df["r"] = np.asarray(next_return)

    out: dict = {"n": int(len(df))}
    out["auc"] = float(roc_auc_score(df["y"], df["p"])) if df["y"].nunique() == 2 else float("nan")

    daily_auc, daily_ic, prec = [], [], []
    for _, g in df.groupby("date"):
        if len(g) < 10:
            continue
        if g["y"].nunique() == 2:
            daily_auc.append(roc_auc_score(g["y"], g["p"]))
        if "r" in g and g["r"].notna().sum() >= 10:
            daily_ic.append(g["p"].corr(g["r"], method="spearman"))
        top = g.nlargest(min(top_k, len(g)), "p")
        prec.append(top["y"].mean())

    out["daily_auc"] = float(np.nanmean(daily_auc)) if daily_auc else float("nan")
    out["daily_ic"] = float(np.nanmean(daily_ic)) if daily_ic else float("nan")
    out["precision_topk"] = float(np.mean(prec)) if prec else float("nan")

    up = df["p"] >= confidence
    down = df["p"] <= 1 - confidence
    picked = up | down
    out["coverage_conf"] = float(picked.mean())
    if picked.any():
        correct = ((up & (df["y"] == 1)) | (down & (df["y"] == 0)))[picked]
        out["hit_rate_conf"] = float(correct.mean())
    else:
        out["hit_rate_conf"] = float("nan")
    return out
