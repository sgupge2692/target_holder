"""
evaluation.py / train.py の評価ロジックのテスト
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "sqlite:////:memory:")

from pipeline.evaluation import (
    walk_forward_splits, split_for_early_stopping, evaluate_predictions,
)


def _panel(n_dates=150, n_codes=40, seed=0, signal=0.0):
    """銘柄コード順に並べた「銘柄 × 日付」パネル（本番の features テーブルと同じ並び）"""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-01", periods=n_dates).strftime("%Y%m%d")
    rows = []
    for c in range(n_codes):
        for d in dates:
            rows.append((f"{1000 + c}", d))
    df = pd.DataFrame(rows, columns=["Code", "Date"])           # Code → Date 順
    df["rsi"] = rng.normal(size=len(df))
    df["ma5_deviation"] = rng.normal(size=len(df))
    df["next_return"] = signal * df["rsi"] * 0.01 + rng.normal(scale=0.01, size=len(df))
    df["label"] = np.where(df["next_return"] > 0, 1, -1)
    return df


# ── 分割 ────────────────────────────────────────────────────────────────

def test_walk_forward_splits_are_chronological_even_if_rows_sorted_by_code():
    df = _panel()
    d = pd.to_datetime(df["Date"])
    splits = list(walk_forward_splits(df["Date"], n_splits=4, embargo_days=2, min_train_dates=20))
    assert len(splits) == 4
    for tr, va in splits:
        assert len(tr) > 0 and len(va) > 0
        assert d.iloc[tr].max() < d.iloc[va].min()               # 学習は必ず検証より過去
        assert not set(tr) & set(va)
        gap_days = d.iloc[va].min() - d.iloc[tr].max()
        assert gap_days >= pd.Timedelta(days=2)                   # embargo


def test_walk_forward_splits_cover_all_dates_in_each_fold():
    """1つの日付が学習と検証に分かれて入ることがない（同日の別銘柄の漏れを防ぐ）"""
    df = _panel()
    for tr, va in walk_forward_splits(df["Date"], n_splits=4, embargo_days=2, min_train_dates=20):
        assert not set(df["Date"].iloc[tr]) & set(df["Date"].iloc[va])


def test_walk_forward_splits_raise_when_too_few_dates():
    df = _panel(n_dates=20)
    with pytest.raises(ValueError):
        list(walk_forward_splits(df["Date"], n_splits=5))


def test_early_stopping_split_is_chronological():
    df = _panel()
    tr, _ = next(iter(walk_forward_splits(df["Date"], n_splits=4, min_train_dates=20)))
    fit, es = split_for_early_stopping(tr, df["Date"])
    d = pd.to_datetime(df["Date"])
    assert d.iloc[fit].max() < d.iloc[es].min()
    assert set(fit) | set(es) <= set(tr)
    assert not set(fit) & set(es)


# ── 指標 ────────────────────────────────────────────────────────────────

def test_metrics_perfect_and_random():
    df = _panel(n_dates=60, n_codes=100)
    y = (df["label"] == 1).astype(int).values
    perfect = evaluate_predictions(df["Date"], y, y * 0.9 + 0.05, df["next_return"].values, top_k=10)
    assert perfect["auc"] == pytest.approx(1.0)
    assert perfect["precision_topk"] == pytest.approx(1.0)
    assert perfect["hit_rate_conf"] == pytest.approx(1.0)
    assert perfect["daily_ic"] > 0.5

    rng = np.random.default_rng(1)
    rand = evaluate_predictions(df["Date"], y, rng.uniform(size=len(y)), df["next_return"].values, top_k=10)
    assert abs(rand["auc"] - 0.5) < 0.06
    assert abs(rand["daily_ic"]) < 0.08


# ── 学習のスモークテスト ────────────────────────────────────────────────

def test_train_full_runs_and_detects_signal(tmp_path, monkeypatch):
    pytest.importorskip("lightgbm")
    import pipeline.train as train

    monkeypatch.setattr(train, "MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(train, "FEATURE_COLS", ["rsi", "ma5_deviation"])
    monkeypatch.setitem(train.DEFAULT_LGBM_PARAMS, "n_estimators", 80)
    monkeypatch.setitem(train.DEFAULT_LGBM_PARAMS, "n_jobs", 1)

    # 信号あり: rsi が翌日リターンに効く → CV AUC は 0.5 を明確に超える
    auc = train.train_full(_panel(n_dates=140, n_codes=30, signal=1.0))
    assert auc > 0.6
    assert (tmp_path / "lgbm_model.pkl").exists()

    # 信号なし（純ノイズ）: AUC は 0.5 付近に留まる（従来の行順分割だと漏れで上振れしやすい）
    auc_noise = train.train_full(_panel(n_dates=140, n_codes=30, seed=3, signal=0.0))
    assert abs(auc_noise - 0.5) < 0.04
