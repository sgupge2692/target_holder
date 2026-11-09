"""
ニュース特徴量を学習に使うかの判断と、A/B 比較のテスト
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
os.environ.setdefault("DATABASE_URL", "sqlite:////:memory:")

from pipeline.news_store import COVERED_COL, NEWS_FEATURE_COLS
from pipeline.train import FEATURE_COLS, resolve_feature_cols


def _features(n_days=40, covered_from=20, n_stocks=5, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2026-06-01", periods=n_days).date
    rows = []
    for di, d in enumerate(dates):
        for s in range(n_stocks):
            rows.append({"Date": d, "Code": f"{s:04d}", COVERED_COL: int(di >= covered_from),
                         **{c: rng.normal() for c in NEWS_FEATURE_COLS}})
    return pd.DataFrame(rows)


def test_news_not_used_when_history_is_short():
    df = _features(n_days=40, covered_from=30)          # 観測 10 日
    cols, out, msg = resolve_feature_cols(df, mode="auto", min_days=90)
    assert not set(NEWS_FEATURE_COLS) & set(cols)
    assert len(out) == len(df)                            # 行も絞らない
    assert "使わない" in msg and "10 日" in msg


def test_news_used_with_enough_history_and_only_covered_rows():
    df = _features(n_days=40, covered_from=10)           # 観測 30 日
    cols, out, msg = resolve_feature_cols(df, mode="auto", min_days=20)
    assert set(NEWS_FEATURE_COLS) <= set(cols) and set(FEATURE_COLS) <= set(cols)
    assert (out[COVERED_COL] == 1).all() and out["Date"].nunique() == 30   # 観測前の行は学習に使わない
    assert "使う" in msg


def test_news_mode_off_and_missing_columns():
    df = _features()
    assert not set(NEWS_FEATURE_COLS) & set(resolve_feature_cols(df, mode="off", min_days=1)[0])
    no_news = df.drop(columns=NEWS_FEATURE_COLS + [COVERED_COL])
    cols, _, msg = resolve_feature_cols(no_news, mode="on", min_days=1)
    assert not set(NEWS_FEATURE_COLS) & set(cols) and "ニュース列が無い" in msg


def test_news_mode_on_with_zero_observed_days_is_not_used():
    df = _features(covered_from=999)
    cols, _, _ = resolve_feature_cols(df, mode="on", min_days=1)
    assert not set(NEWS_FEATURE_COLS) & set(cols)


def _panel(n_days, n_stocks, news_signal: bool, seed=0):
    """ニュースが翌日の超過リターンに効く世界 / 効かない世界の合成データ"""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2026-01-05", periods=n_days).date
    rows = []
    for d in dates:
        for s in range(n_stocks):
            tech = rng.normal()
            news = rng.normal()
            noise = rng.normal()
            y = (0.8 * tech + (1.5 * news if news_signal else 0) + noise)
            rows.append({"Date": d, "Code": f"{s:04d}", "f1": tech, "f2": rng.normal(),
                         "news_sentiment": news, "label_excess": 1 if y > 0 else -1, "excess_return": y * 0.01})
    return pd.DataFrame(rows)


def test_ablation_detects_useful_news_and_ignores_useless_news():
    from pipeline.news_ablation import compare_feature_sets
    useful = compare_feature_sets(_panel(120, 40, True), ["f1", "f2"], ["news_sentiment"], n_splits=3)
    assert useful["folds"] and useful["delta"]["auc"] > 0.05            # 効くニュースは AUC が明確に上がる

    useless = compare_feature_sets(_panel(120, 40, False, seed=3), ["f1", "f2"], ["news_sentiment"], n_splits=3)
    assert abs(useless["delta"]["auc"]) < 0.03                          # 効かないニュースでは差が出ない
    assert useless["n_dates"] == 120


def test_add_news_sentiment_uses_stored_articles_only():
    """features に付くニュース列は、蓄積した記事から時点ごとに作られる（今日の値を全期間に付けない）"""
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import create_engine, text
    from pipeline.feature_engineering import add_news_sentiment

    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("""CREATE TABLE news_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, url_hash TEXT, title TEXT, source TEXT,
            published_at TEXT, first_seen_at TEXT, score REAL, urgency REAL, UNIQUE (code, url_hash))"""))
        seen = datetime(2026, 11, 6, 8, 0, tzinfo=timezone.utc)
        for i, code in enumerate(["0000", "7203"]):
            c.execute(text("""INSERT INTO news_articles (code,url_hash,title,first_seen_at,score,urgency)
                              VALUES (:c,:h,'t',:s,:sc,0)"""),
                      {"c": code, "h": str(i), "s": seen.isoformat(), "sc": 0.9 if code == "7203" else 0.0})
    df = pd.DataFrame([(c, d) for c in ["7203"] for d in pd.bdate_range("2026-10-01", "2026-11-06").date],
                      columns=["Code", "Date"])
    out = add_news_sentiment(df.copy(), engine)
    hist = out[pd.to_datetime(out["Date"]) < pd.Timestamp("2026-11-06")]
    assert (hist[NEWS_FEATURE_COLS].to_numpy() == 0).all()
    assert out.iloc[-1]["news_article_count"] == 1 and out.iloc[-1]["news_sentiment"] == pytest.approx(0.9)


def test_collect_exit_code_flags_total_fetch_failure():
    from pipeline.collect_news import exit_code
    assert exit_code(10, 0, 120, {"ok": 30, "errors": 0}) == 0
    assert exit_code(10, 0, 0, {"ok": 0, "errors": 30}) == 1       # ネットワーク断: 記事 0 件でも成功扱いにしない
    assert exit_code(10, 10, 0, {"ok": 0, "errors": 0}) == 1       # 全銘柄で例外
    assert exit_code(10, 0, 0, {"ok": 30, "errors": 0}) == 0       # 取得はできたが新着が無い → 成功
    assert exit_code(10, 0, 5, {"ok": 10, "errors": 20}) == 0      # 一部失敗は警告のみ
