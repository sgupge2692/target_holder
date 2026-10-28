"""
predict.py のユニットテスト
"""
import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "sqlite:////:memory:")

from pipeline.predict import get_top_features, FEATURE_LABELS


# ── get_top_features テスト ───────────────────────────────────────────────

class MockModel:
    """特徴量重要度を返すモッククラス"""
    def __init__(self, importances: dict):
        self._importances = importances

    def feature_importances_(self, cols):
        return np.array([self._importances.get(c, 0) for c in cols])

    # LightGBM のインターフェースを模倣
    class _feature_importances:
        pass


def _make_lgbm_mock(feature_cols, importances_list):
    """lightgbm.Booster に近い構造のモック"""
    import types
    m = types.SimpleNamespace()
    arr = np.array(importances_list)
    m.feature_importance = lambda importance_type="gain": arr
    m.feature_name = lambda: feature_cols
    return m


def test_get_top_features_returns_n(monkeypatch):
    """n 件返すことを確認"""
    import pipeline.predict as pred_module

    cols = ["rsi_14", "close_to_ma5", "volume_ratio", "macd_signal", "sma_20"]
    importances = [50.0, 40.0, 30.0, 20.0, 10.0]
    mock_lgbm = _make_lgbm_mock(cols, importances)

    feat_values = {c: float(i) for i, c in enumerate(cols)}
    result = pred_module.get_top_features(mock_lgbm, feat_values, n=3, feat_cols=cols)

    assert len(result) == 3


def test_get_top_features_sorted_by_importance(monkeypatch):
    """重要度順にソートされていることを確認"""
    import pipeline.predict as pred_module

    cols = ["a", "b", "c", "d", "e"]
    importances = [10.0, 50.0, 30.0, 70.0, 20.0]
    mock_lgbm = _make_lgbm_mock(cols, importances)

    feat_values = {c: 1.0 for c in cols}
    result = pred_module.get_top_features(mock_lgbm, feat_values, n=3, feat_cols=cols)

    scores = [r["importance"] for r in result]
    assert scores == sorted(scores, reverse=True)
    # 上位3件は d, b, c
    names = [r["feature"] for r in result]
    assert names[0] in ("d", FEATURE_LABELS.get("d", "d"))


def test_get_top_features_with_missing_feat_cols(monkeypatch):
    """feat_cols が None のときも動作する（FEATURE_COLS フォールバック）"""
    import pipeline.predict as pred_module

    # FEATURE_COLS の最初の5件を使う
    cols = pred_module.FEATURE_COLS[:5]
    importances = list(range(len(cols), 0, -1))
    mock_lgbm = _make_lgbm_mock(cols, importances)

    feat_values = {c: 1.0 for c in cols}
    # feat_cols=None → FEATURE_COLS を使う
    result = pred_module.get_top_features(mock_lgbm, feat_values, n=3, feat_cols=None)
    assert len(result) == 3


# ── FEATURE_LABELS テスト ─────────────────────────────────────────────────

def test_feature_labels_is_dict():
    assert isinstance(FEATURE_LABELS, dict)


def test_feature_labels_has_entries():
    assert len(FEATURE_LABELS) >= 10  # 最低10件あるはず


def test_feature_labels_values_are_strings():
    assert all(isinstance(v, str) for v in FEATURE_LABELS.values())
