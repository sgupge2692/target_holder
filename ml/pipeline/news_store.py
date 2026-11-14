"""
ニュースの蓄積と、時点整合（point-in-time）のニュース特徴量

■ なぜ作り直したか
  旧実装は「今日取得したニュースのスコア」を、過去すべての日付の行に同じ値で付けていた。
  学習データでは銘柄ごとの固定値になり、銘柄IDを教えているのと同じ（リークかつ無意味）。
  RSS は直近の記事しか返さないので、過去日のニュースを後から取り直すこともできない。

■ 方針
  1. 毎日 collect_news.py でニュースを DB（news_articles）に蓄積する
  2. 記事が「使えるようになった時刻」は、こちらが初めて見た時刻 first_seen_at とする
     （本番でその時点に実際に持っていた情報と、学習時の情報を一致させるため）
  3. 各日 t の特徴量は、予測時刻 t の CUTOFF_HOUR 時（JST）までに見られた記事だけで作る
  4. 蓄積期間が足りないうちは、ニュース特徴量を学習に使わない（train.py）
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

import numpy as np
import pandas as pd
from sqlalchemy import text

JST = timezone(timedelta(hours=9))

# 予測を作る時刻（JST）。cron は 18:50 に配信するので、18 時までに見た記事を使う。
CUTOFF_HOUR = int(os.getenv("NEWS_CUTOFF_HOUR", "18"))
POS_THRESHOLD = 0.05   # 記事スコアがこれより大きければポジティブ、-これより小さければネガティブ

NEWS_FEATURE_COLS = [
    "news_sentiment",      # 直近3日の記事スコア平均 [-1, +1]
    "news_sent_1d",        # 直近1日の記事スコア平均
    "news_pos_count",      # 直近3日のポジティブ記事数
    "news_neg_count",      # 直近3日のネガティブ記事数
    "news_article_count",  # 直近3日の記事数
    "news_count_1d",       # 直近1日の記事数
    "news_urgency",        # 直近3日の速報ワード含有率の平均 [0, 1]
]
COVERED_COL = "news_covered"   # この日は3日分の記事を観測できていたか（1/0）。モデルの入力にはしない


# ────────────────────────────────────────────────────────────────
# 記事の整形
# ────────────────────────────────────────────────────────────────

def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """日時を UTC の aware にそろえる。タイムゾーンが無ければ JST とみなす。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(timezone.utc)


def url_hash(link: str, title: str) -> str:
    return hashlib.md5((link or title).encode("utf-8")).hexdigest()


def article_row(code: str, item: dict, now: datetime, max_age_hours: int = 72) -> Optional[dict]:
    """
    RSS / API の1件を DB 行にする。古すぎる記事・タイトルが空の記事は None。
    item: {"title","description","pubDate","link","source"}
    """
    from news_sentiment import parse_pubdate, urgency_score, weighted_score

    title = (item.get("title") or "").strip()
    if not title:
        return None
    published = to_utc(parse_pubdate(item.get("pubDate", "")))
    if published is not None and (now - published) > timedelta(hours=max_age_hours):
        return None   # 古い記事を「いま見つけた」ことにして最新ニュース扱いしない
    text_ = title + " " + (item.get("description") or "")
    return {
        "code": code,
        "url_hash": url_hash(item.get("link", ""), title),
        "title": title[:500],
        "source": item.get("source"),
        "published_at": published,
        "first_seen_at": now,
        "score": weighted_score(text_),
        "urgency": urgency_score(title),
    }


def available_at(first_seen_at: pd.Series, published_at: pd.Series) -> pd.Series:
    """
    記事が使えるようになった時刻 = こちらが初めて見た時刻。
    公開時刻のほうが後になっているデータ（時計のずれ等）は、公開時刻に合わせる。
    """
    fs = pd.to_datetime(first_seen_at, utc=True)
    pub = pd.to_datetime(published_at, utc=True)
    return fs.where(pub.isna() | (fs >= pub), pub)


# ────────────────────────────────────────────────────────────────
# DB
# ────────────────────────────────────────────────────────────────

def save_articles(engine, rows: Iterable[dict]) -> int:
    """記事を保存する（(code, url_hash) が同じものは無視）。保存を試みた件数を返す。"""
    rows = list(rows)
    if not rows:
        return 0
    sql = text("""
        INSERT INTO news_articles (code, url_hash, title, source, published_at, first_seen_at, score, urgency)
        VALUES (:code, :url_hash, :title, :source, :published_at, :first_seen_at, :score, :urgency)
        ON CONFLICT (code, url_hash) DO NOTHING
    """)
    with engine.begin() as conn:
        conn.execute(sql, rows)
    return len(rows)


def load_articles(engine) -> pd.DataFrame:
    """蓄積した記事を、available_at つきで読む。テーブルが無い・空なら空の DataFrame。"""
    cols = ["code", "available_at", "score", "urgency"]
    try:
        df = pd.read_sql(
            "SELECT code, first_seen_at, published_at, score, urgency FROM news_articles", engine
        )
    except Exception:
        return pd.DataFrame(columns=cols)
    if df.empty:
        return pd.DataFrame(columns=cols)
    df["available_at"] = available_at(df["first_seen_at"], df["published_at"])
    return df[cols]


# ────────────────────────────────────────────────────────────────
# 時点整合の特徴量
# ────────────────────────────────────────────────────────────────

def _cutoff_ns(dates: pd.Series, cutoff_hour: int) -> np.ndarray:
    """各日の予測時刻（JST の cutoff_hour 時）を UTC のナノ秒で返す"""
    d = pd.to_datetime(dates).dt.tz_localize(None).dt.normalize()
    cut = (d + pd.Timedelta(hours=cutoff_hour)).dt.tz_localize(JST).dt.tz_convert("UTC")
    return cut.map(lambda x: x.value).to_numpy(dtype="int64")


def build_point_in_time_features(
    keys: pd.DataFrame,
    articles: pd.DataFrame,
    cutoff_hour: int = CUTOFF_HOUR,
) -> pd.DataFrame:
    """
    各 (Code, Date) について、その日の予測時刻までに見られた記事だけで特徴量を作る。

    keys     : Code, Date の列を持つ DataFrame
    articles : code, available_at(UTC), score, urgency（load_articles の結果）
    Returns  : keys と同じ index の DataFrame（NEWS_FEATURE_COLS + news_covered）
    """
    out = pd.DataFrame(0.0, index=keys.index, columns=NEWS_FEATURE_COLS + [COVERED_COL])
    out[COVERED_COL] = 0
    if keys.empty or articles is None or articles.empty:
        return out

    art = articles.copy()
    art["t"] = pd.to_datetime(art["available_at"], utc=True).map(lambda x: x.value)
    first_seen = int(art["t"].min())

    day = 24 * 3600 * 10**9
    cut_all = _cutoff_ns(keys["Date"], cutoff_hour)
    # 3日分の窓がすべて観測期間に入っている日だけ「カバー済み」
    out[COVERED_COL] = (cut_all - 3 * day >= first_seen).astype(int)

    by_code = {c: g.sort_values("t") for c, g in art.groupby("code")}
    pos_idx = {c: keys.index[keys["Code"] == c] for c in by_code if (keys["Code"] == c).any()}

    for code, idx in pos_idx.items():
        g = by_code[code]
        t = g["t"].to_numpy()
        score = g["score"].to_numpy(dtype=float)
        urg = g["urgency"].to_numpy(dtype=float)
        pos = (score > POS_THRESHOLD).astype(float)
        neg = (score < -POS_THRESHOLD).astype(float)

        def cum(a):
            return np.concatenate([[0.0], np.cumsum(a)])

        c_score, c_urg, c_pos, c_neg = cum(score), cum(urg), cum(pos), cum(neg)
        cut = cut_all[keys.index.get_indexer(idx)]
        hi = np.searchsorted(t, cut, side="right")
        lo3 = np.searchsorted(t, cut - 3 * day, side="right")
        lo1 = np.searchsorted(t, cut - 1 * day, side="right")

        n3, n1 = hi - lo3, hi - lo1
        with np.errstate(invalid="ignore", divide="ignore"):
            mean3 = np.where(n3 > 0, (c_score[hi] - c_score[lo3]) / np.maximum(n3, 1), 0.0)
            mean1 = np.where(n1 > 0, (c_score[hi] - c_score[lo1]) / np.maximum(n1, 1), 0.0)
            urg3 = np.where(n3 > 0, (c_urg[hi] - c_urg[lo3]) / np.maximum(n3, 1), 0.0)

        out.loc[idx, "news_sentiment"] = mean3
        out.loc[idx, "news_sent_1d"] = mean1
        out.loc[idx, "news_pos_count"] = c_pos[hi] - c_pos[lo3]
        out.loc[idx, "news_neg_count"] = c_neg[hi] - c_neg[lo3]
        out.loc[idx, "news_article_count"] = n3
        out.loc[idx, "news_count_1d"] = n1
        out.loc[idx, "news_urgency"] = urg3

    return out


def covered_days(df: pd.DataFrame) -> int:
    """ニュースを観測できていた日の数（features テーブルから）"""
    if COVERED_COL not in df.columns or df.empty:
        return 0
    return int(df.loc[df[COVERED_COL] == 1, "Date"].nunique())
