"""
ニュースの蓄積と時点整合の特徴量のテスト

いちばん守りたいのは「ある日の特徴量に、その日の予測時刻より後の記事が入らない」こと。
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
os.environ.setdefault("DATABASE_URL", "sqlite:////:memory:")

from pipeline.news_store import (
    COVERED_COL, JST, NEWS_FEATURE_COLS, article_row, available_at,
    build_point_in_time_features, covered_days, load_articles, save_articles,
)

DAYS = pd.bdate_range("2026-10-01", "2026-11-06").date


def jst(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=JST).astimezone(timezone.utc)


def keys_for(codes, dates=DAYS):
    return pd.DataFrame([(c, d) for c in codes for d in dates], columns=["Code", "Date"])


def arts(rows):
    """rows: [(code, available_at(datetime), score)]"""
    return pd.DataFrame(
        [{"code": c, "available_at": t, "score": s, "urgency": 0.0} for c, t, s in rows]
    )


def at(feats, keys, code, date):
    i = keys.index[(keys["Code"] == code) & (keys["Date"] == date)][0]
    return feats.loc[i]


# 蓄積の開始を早い日に置くための番兵（観測期間を長くする）
SENTINEL = ("0000", jst(2026, 10, 1, 9), 0.0)


def test_article_after_cutoff_goes_to_next_day_not_same_day():
    keys = keys_for(["7203"])
    a = arts([SENTINEL, ("7203", jst(2026, 11, 4, 18, 30), 0.8)])   # 11/4 18:30（予測時刻 18:00 の後）
    f = build_point_in_time_features(keys, a)
    d4, d5 = datetime(2026, 11, 4).date(), datetime(2026, 11, 5).date()
    assert at(f, keys, "7203", d4)["news_article_count"] == 0       # 11/4 の予測には入らない
    assert at(f, keys, "7203", d5)["news_article_count"] == 1       # 11/5 から使える
    assert at(f, keys, "7203", d5)["news_sent_1d"] == pytest.approx(0.8)


def test_article_exactly_at_cutoff_is_included():
    keys = keys_for(["7203"])
    a = arts([SENTINEL, ("7203", jst(2026, 11, 4, 18, 0), 0.5)])
    f = build_point_in_time_features(keys, a)
    assert at(f, keys, "7203", datetime(2026, 11, 4).date())["news_article_count"] == 1


def test_windows_1d_and_3d():
    keys = keys_for(["7203"])
    a = arts([
        SENTINEL,
        ("7203", jst(2026, 11, 2, 12), -1.0),   # 11/5 18:00 から見て 3日と6時間前 → 3日窓の外
        ("7203", jst(2026, 11, 3, 12), 0.6),    # 2日前 → 3日窓のみ
        ("7203", jst(2026, 11, 5, 9), 0.2),     # 当日 → 1日窓にも入る
    ])
    f = at(build_point_in_time_features(keys, a), keys, "7203", datetime(2026, 11, 5).date())
    assert f["news_article_count"] == 2 and f["news_count_1d"] == 1
    assert f["news_sentiment"] == pytest.approx((0.6 + 0.2) / 2)
    assert f["news_sent_1d"] == pytest.approx(0.2)
    assert f["news_pos_count"] == 2 and f["news_neg_count"] == 0


def test_future_article_never_changes_past_features():
    """未来の記事を足しても、それより前の日の特徴量は 1 つも変わらない（リークが無い）"""
    keys = keys_for(["7203", "9984"])
    base_rows = [SENTINEL, ("7203", jst(2026, 10, 20, 10), 0.4), ("9984", jst(2026, 10, 22, 10), -0.7)]
    future = ("7203", jst(2026, 11, 5, 10), 0.9)
    f0 = build_point_in_time_features(keys, arts(base_rows))
    f1 = build_point_in_time_features(keys, arts(base_rows + [future]))

    past = pd.to_datetime(keys["Date"]) < pd.Timestamp("2026-11-05")
    pd.testing.assert_frame_equal(f0[past.values], f1[past.values])
    assert (f0[~past.values][NEWS_FEATURE_COLS].values != f1[~past.values][NEWS_FEATURE_COLS].values).any()


def test_features_are_per_stock():
    keys = keys_for(["7203", "9984"])
    a = arts([SENTINEL, ("7203", jst(2026, 11, 4, 10), 0.9)])
    f = build_point_in_time_features(keys, a)
    d = datetime(2026, 11, 5).date()
    assert at(f, keys, "7203", d)["news_article_count"] == 1
    assert at(f, keys, "9984", d)["news_article_count"] == 0


def test_todays_news_does_not_leak_into_history():
    """旧実装のバグ: 今日の記事のスコアが過去すべての日付に付いていた。今は付かない"""
    keys = keys_for(["7203"])
    a = arts([SENTINEL, ("7203", jst(2026, 11, 6, 10), 0.9)])    # 最終日にだけ記事
    f = build_point_in_time_features(keys, a)
    history = f[pd.to_datetime(keys["Date"]) < pd.Timestamp("2026-11-06")]
    assert (history[NEWS_FEATURE_COLS].to_numpy() == 0).all()


def test_covered_flag_needs_three_days_of_observation():
    keys = keys_for(["7203"])
    a = arts([("7203", jst(2026, 10, 15, 10), 0.1)])     # 観測開始 10/15 10:00（JST）
    f = build_point_in_time_features(keys, a)
    # 3日窓が観測期間に収まるのは、予測時刻(18:00) - 72h >= 10/15 10:00 となる 10/18 以降
    assert at(f, keys, "7203", datetime(2026, 10, 15).date())[COVERED_COL] == 0
    assert at(f, keys, "7203", datetime(2026, 10, 16).date())[COVERED_COL] == 0
    assert at(f, keys, "7203", datetime(2026, 10, 19).date())[COVERED_COL] == 1
    assert covered_days(pd.concat([keys, f[[COVERED_COL]]], axis=1)) > 0


def test_empty_articles_gives_zero_and_not_covered():
    keys = keys_for(["7203"])
    f = build_point_in_time_features(keys, pd.DataFrame(columns=["code", "available_at", "score", "urgency"]))
    assert (f[NEWS_FEATURE_COLS].to_numpy() == 0).all() and (f[COVERED_COL] == 0).all()


def test_available_at_is_first_seen_unless_published_later():
    fs = pd.Series([pd.Timestamp("2026-11-05 08:00", tz="UTC")] * 3)
    pub = pd.Series([pd.Timestamp("2026-11-05 01:00", tz="UTC"),    # 公開のほうが前 → 初めて見た時刻
                     pd.Timestamp("2026-11-05 09:00", tz="UTC"),    # 公開のほうが後（時計のずれ）→ 公開時刻
                     pd.NaT])
    out = available_at(fs, pub)
    assert out.iloc[0] == fs.iloc[0] and out.iloc[1] == pub.iloc[1] and out.iloc[2] == fs.iloc[2]


def test_article_row_drops_old_and_empty_articles():
    now = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)
    fresh = article_row("7203", {"title": "トヨタ 上方修正", "pubDate": "Mon, 09 Nov 2026 05:00:00 +0000",
                                 "link": "http://x/1", "source": "yahoo"}, now)
    assert fresh["score"] > 0 and fresh["first_seen_at"] == now and fresh["source"] == "yahoo"
    old = article_row("7203", {"title": "古い記事", "pubDate": "Mon, 02 Nov 2026 05:00:00 +0000", "link": "http://x/2"}, now)
    assert old is None
    assert article_row("7203", {"title": "  ", "link": "http://x/3"}, now) is None


def test_save_dedupes_and_load_roundtrip():
    from sqlalchemy import create_engine, text
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("""CREATE TABLE news_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, url_hash TEXT, title TEXT, source TEXT,
            published_at TEXT, first_seen_at TEXT, score REAL, urgency REAL, UNIQUE (code, url_hash))"""))
    now = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)
    row = article_row("7203", {"title": "トヨタ 増益", "pubDate": "Mon, 09 Nov 2026 05:00:00 +0000", "link": "http://x/1"}, now)
    save_articles(engine, [row])
    save_articles(engine, [row])                      # 同じ記事を翌日も取得しても二重に入らない
    df = load_articles(engine)
    assert len(df) == 1 and df.iloc[0]["code"] == "7203" and df.iloc[0]["score"] > 0
    assert pd.api.types.is_datetime64_any_dtype(df["available_at"])


def test_load_articles_without_table_is_empty():
    from sqlalchemy import create_engine
    assert load_articles(create_engine("sqlite://")).empty
