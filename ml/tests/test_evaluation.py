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


# ── 市場超過リターンのラベル ────────────────────────────────────────────

def _excess_panel():
    """3日 × 5銘柄。日ごとに市場全体が動き、そのうえで銘柄ごとに差がつくデータ"""
    from pipeline.feature_engineering import add_excess_labels
    market = {"2024-01-04": -0.02, "2024-01-05": 0.00, "2024-01-09": 0.03}
    rel = [-0.02, -0.005, 0.0, 0.005, 0.02]       # 銘柄ごとの市場比
    rows = []
    for d, m in market.items():
        for i, r in enumerate(rel):
            rows.append({"Date": pd.Timestamp(d), "Code": f"{1000 + i}",
                         "next_return": m + r, "label_threshold": 0.01})
    return add_excess_labels(pd.DataFrame(rows))


def test_excess_label_removes_market_move():
    df = _excess_panel()
    # 市場が -2% の日でも、市場より強い銘柄は OUTPERFORM になる（絶対リターンでは負でも）
    crash = df[df["Date"] == pd.Timestamp("2024-01-04")].set_index("Code")
    assert crash.loc["1004", "next_return"] == pytest.approx(0.0)       # 絶対リターンは 0%
    assert crash.loc["1004", "label_excess"] == 1                        # でも市場比では +2%
    assert crash.loc["1000", "label_excess"] == -1
    # 日ごとの超過リターンの中央値は 0
    assert df.groupby("Date")["excess_return"].median().abs().max() < 1e-12


def test_excess_label_balanced_regardless_of_market_direction():
    """市場が大きく上がる日・下がる日でも、UP/DOWN ラベルが偏らない"""
    df = _excess_panel()
    for _, g in df.groupby("Date"):
        assert (g["label_excess"] == 1).sum() == (g["label_excess"] == -1).sum() == 2


def test_excess_label_neutral_band():
    df = _excess_panel()
    # しきい値 0.01 × 0.3 = 0.003 未満の超過リターンは中立（学習対象外）
    assert (df.loc[df["excess_return"].abs() < 0.003, "label_excess"] == 0).all()
    assert (df.loc[df["excess_return"].abs() >= 0.003, "label_excess"] != 0).all()


def test_train_prefers_excess_target_and_falls_back(tmp_path, monkeypatch):
    import pipeline.train as train
    df = _panel(n_dates=30, n_codes=10)
    df["label_excess"] = np.where(df["rsi"] > 0, 1, -1)
    df["excess_return"] = df["rsi"] * 0.01
    monkeypatch.setattr(train, "FEATURE_COLS", ["rsi", "ma5_deviation"])

    X, y, _, _, meta = train.prepare_data_with_meta(df)
    assert (y.values == (X["rsi"].values > 0).astype(int)).all()         # label_excess を使っている
    assert np.allclose(meta["next_return"].values, X["rsi"].values * 0.01)

    X2, y2, _, _, _ = train.prepare_data_with_meta(df.drop(columns=["label_excess", "excess_return"]))
    assert len(y2) == len(df)                                              # 旧データは label にフォールバック


# ── バックテスト: 超過リターンでの的中判定 ───────────────────────────────

def test_backtest_judges_by_excess_return():
    from pipeline.backtest import judge_signal, calc_next_day_returns
    assert judge_signal("UP", 0.004) is True
    assert judge_signal("UP", -0.004) is False
    assert judge_signal("DOWN", -0.004) is True
    assert judge_signal("DOWN", 0.004) is False
    assert judge_signal("NEUTRAL", 0.1) is None

    # 市場が -2% の日: 株価が -1% で済んだ銘柄は UP 的中（超過 +1%）
    quotes = pd.DataFrame([
        ("1001", "2024-01-04", 100.0), ("1001", "2024-01-05", 99.0),   # -1%
        ("1002", "2024-01-04", 100.0), ("1002", "2024-01-05", 98.0),   # -2%
        ("1003", "2024-01-04", 100.0), ("1003", "2024-01-05", 97.0),   # -3%
        ("1004", "2024-01-04", 100.0),                                  # 翌日データなし → 除外
    ], columns=["Code", "Date", "AdjustmentClose"])
    from datetime import date
    ret = calc_next_day_returns(quotes, date(2024, 1, 4))
    assert set(ret.index) == {"1001", "1002", "1003"}
    market = float(ret.median())
    assert market == pytest.approx(-0.02)
    assert judge_signal("UP", ret["1001"] - market) is True
    assert judge_signal("UP", ret["1003"] - market) is False


# ── 確率の校正 ──────────────────────────────────────────────────────────

def _overconfident(n=6000, seed=0):
    """真の上昇確率は 0.4〜0.6 だが、モデルは 0.1〜0.9 と過信して出力するケース"""
    rng = np.random.default_rng(seed)
    true_p = rng.uniform(0.4, 0.6, n)
    y = (rng.uniform(size=n) < true_p).astype(int)
    z = (true_p - 0.5) * 20                       # 傾きを 5 倍に増幅（過信）
    return 1 / (1 + np.exp(-z)), y, true_p


def test_platt_reduces_calibration_error_and_keeps_ranking():
    from pipeline.evaluation import fit_platt, apply_platt, expected_calibration_error
    p, y, _ = _overconfident()
    params = fit_platt(p, y)
    cal = apply_platt(p, params)

    assert expected_calibration_error(y, cal) < expected_calibration_error(y, p) / 3
    assert (np.argsort(p, kind="stable") == np.argsort(cal, kind="stable")).all()   # 順位は不変
    assert 0.35 < cal.min() and cal.max() < 0.65                                     # 確率が実力の範囲に収まる


def test_calibration_report_validates_on_future_folds():
    from pipeline.evaluation import calibration_report
    p, y, _ = _overconfident(n=6000)
    fold = np.repeat(np.arange(1, 7), 1000)
    params, m = calibration_report(p, y, fold)

    assert m["ece_calibrated"] < m["ece_raw"]
    assert m["brier_calibrated"] <= m["brier_raw"]
    assert set(m["threshold_table"]) == {"0.52", "0.55", "0.60", "0.65"}
    # 校正後は確度60%以上のシグナルがほぼ出なくなる（実力が 40〜60% の相手に 90% とは言えない）
    assert m["threshold_table"]["0.65"]["coverage"] < 0.01
    assert set(params) == {"a", "b"}


def test_train_saves_calibrator_and_predict_applies_it(tmp_path, monkeypatch):
    pytest.importorskip("lightgbm")
    import joblib
    import pipeline.train as train
    from pipeline.predict import apply_calibration

    monkeypatch.setattr(train, "MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(train, "FEATURE_COLS", ["rsi", "ma5_deviation"])
    monkeypatch.setitem(train.DEFAULT_LGBM_PARAMS, "n_estimators", 60)
    monkeypatch.setitem(train.DEFAULT_LGBM_PARAMS, "n_jobs", 1)

    train.train_full(_panel(n_dates=140, n_codes=30, signal=1.0))
    params = joblib.load(tmp_path / "calibrator.pkl")
    assert set(params) == {"a", "b"}
    metrics = joblib.load(tmp_path / "metrics.pkl")
    assert "ece_calibrated" in metrics

    p = np.array([0.1, 0.5, 0.9])
    cal = apply_calibration(p, params)
    assert (np.diff(cal) > 0).all()                       # 単調増加
    assert np.array_equal(apply_calibration(p, None), p)  # 校正器が無ければそのまま
