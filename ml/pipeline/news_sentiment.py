"""
ニュースセンチメント特徴量生成モジュール v2

取得ソース（優先順）:
  1. Yahoo Finance Japan RSS  — 社名 / 銘柄コード検索
  2. Google News RSS (ja)     — 社名検索
  3. NewsAPI                  — NEWSAPI_KEY 環境変数があれば使用

スコアリング:
  - 辞書ベース (重み付き TF-IDF 風)
  - NEWS_USE_LLM=true の場合は gpt-4o-mini でバッチ分析

追加特徴量:
  - news_sentiment        : [-1, +1] 総合スコア
  - news_pos_count        : ポジティブ記事数
  - news_neg_count        : ネガティブ記事数
  - news_article_count    : 取得記事総数
  - news_urgency          : 速報・緊急ワード含有率 [0, 1]
  - news_sector_sentiment : セクター全体センチメント [-1, +1]

キャッシュ:
  - メモリキャッシュ (TTL=30分) で同一銘柄の重複リクエストを防止

使用方法:
  単体テスト: python pipeline/news_sentiment.py --code 7203 --name トヨタ
"""

import os
import re
import time
import json
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional
from functools import lru_cache
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

JST = timezone(timedelta(hours=9))

# ── 環境変数 ──────────────────────────────────────────────────────────────
NEWSAPI_KEY       = os.getenv("NEWSAPI_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
USE_LLM_SENTIMENT = bool(OPENAI_API_KEY) and os.getenv("NEWS_USE_LLM", "false").lower() == "true"
NEWS_CACHE_TTL    = int(os.getenv("NEWS_CACHE_TTL_MINUTES", "30")) * 60  # 秒に変換

# 取得の成否の集計（collect_news.py が「全部失敗していたのに成功扱い」にならないよう確認する）
FETCH_STATS = {"ok": 0, "errors": 0}

# ── メモリキャッシュ ──────────────────────────────────────────────────────
_CACHE: dict[str, tuple[float, list[dict]]] = {}  # key → (timestamp, items)

def _cache_get(key: str) -> Optional[list[dict]]:
    entry = _CACHE.get(key)
    if entry and (time.time() - entry[0]) < NEWS_CACHE_TTL:
        return entry[1]
    return None

def _cache_set(key: str, items: list[dict]) -> None:
    _CACHE[key] = (time.time(), items)


# ── 重み付き辞書 ─────────────────────────────────────────────────────────

# weight: 重要語ほど高い（最大3.0）
POSITIVE_WORDS: list[tuple[str, float]] = [
    # 業績改善系（高影響）
    ("上方修正", 3.0), ("過去最高益", 3.0), ("最高益", 2.5), ("大幅増益", 2.5),
    ("増収増益", 2.5), ("目標株価引き上げ", 2.0), ("格上げ", 2.0),
    ("特需", 2.0), ("大型受注", 2.0), ("買収", 1.8), ("提携", 1.5),
    # 一般ポジティブ（低影響）
    ("増収", 1.5), ("増益", 1.5), ("黒字", 1.5), ("好調", 1.2), ("好業績", 1.2),
    ("買い推奨", 1.8), ("買い", 1.0), ("強気", 1.0), ("急騰", 1.5), ("新高値", 1.5),
    ("上昇", 1.0), ("拡大", 1.0), ("増加", 1.0), ("改善", 1.0), ("成長", 1.0),
    ("回復", 1.0), ("反発", 1.0), ("増配", 1.5), ("自社株買い", 1.8),
    ("新製品", 1.2), ("新サービス", 1.2), ("出資", 1.2), ("受注", 1.2),
]

NEGATIVE_WORDS: list[tuple[str, float]] = [
    # 業績悪化系（高影響）
    ("下方修正", 3.0), ("最終赤字", 3.0), ("大幅減益", 2.5), ("損失計上", 2.5),
    ("無配", 2.5), ("行政処分", 2.5), ("不祥事", 2.0), ("不正会計", 2.5),
    ("民事再生", 3.0), ("倒産", 3.0), ("目標株価引き下げ", 2.0), ("格下げ", 2.0),
    # 一般ネガティブ（低影響）
    ("減収", 1.5), ("減益", 1.5), ("赤字", 1.5), ("不調", 1.2), ("悪化", 1.2),
    ("売り推奨", 1.8), ("売り", 1.0), ("弱気", 1.0), ("急落", 1.5), ("安値更新", 1.5),
    ("下落", 1.0), ("縮小", 1.0), ("減少", 1.0), ("低迷", 1.0), ("後退", 1.0),
    ("不振", 1.0), ("反落", 1.0), ("減配", 1.5), ("訴訟", 1.5), ("リコール", 1.8),
    ("リストラ", 1.5), ("解雇", 1.2), ("調査", 0.8),
]

# 速報・緊急ワード
URGENCY_WORDS = ["速報", "緊急", "急騰", "急落", "ストップ高", "ストップ安", "サーキットブレーカー", "臨時", "緊急声明"]

# セクターキーワード（セクターコード → 検索語）
SECTOR_KEYWORDS: dict[str, list[str]] = {
    "0050": ["自動車", "EV", "電気自動車"],
    "3050": ["半導体", "チップ", "AI半導体"],
    "3150": ["通信", "5G", "携帯"],
    "3250": ["製薬", "医薬品", "新薬"],
    "7050": ["銀行", "金融", "利上げ"],
    "3350": ["商社", "資源", "原油"],
    "0150": ["鉄鋼", "素材", "資材"],
    "3500": ["不動産", "住宅", "REIT"],
    "3700": ["小売", "消費", "百貨店"],
    "3800": ["外食", "食品", "飲料"],
}


# ── スコア計算 ────────────────────────────────────────────────────────────

def weighted_score(text: str) -> float:
    """
    重み付き辞書スコア。[-1, +1] を返す。
    長いテキストほど正規化が効くように調整。
    """
    pos_w = sum(w for word, w in POSITIVE_WORDS if word in text)
    neg_w = sum(w for word, w in NEGATIVE_WORDS if word in text)
    total = pos_w + neg_w
    if total == 0:
        return 0.0
    # sigmoid-like 正規化
    raw = (pos_w - neg_w) / total
    return round(float(raw), 4)


def urgency_score(text: str) -> float:
    """速報ワードの含有率 [0, 1]"""
    hits = sum(1 for w in URGENCY_WORDS if w in text)
    return min(hits / 3.0, 1.0)


# ── フェッチ関数 ──────────────────────────────────────────────────────────

def _fetch_rss(url: str, cache_key: str, max_items: int = 20) -> list[dict]:
    """汎用 RSS フェッチャー（キャッシュ付き）"""
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (compatible)"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = []
        for item in root.iter("item"):
            title   = item.findtext("title")       or ""
            desc    = item.findtext("description") or ""
            pub     = item.findtext("pubDate")     or ""
            link    = item.findtext("link")        or ""
            items.append({"title": title, "description": desc, "pubDate": pub, "link": link})
            if len(items) >= max_items:
                break
        _cache_set(cache_key, items)
        FETCH_STATS["ok"] += 1
        return items
    except Exception as e:
        FETCH_STATS["errors"] += 1
        print(f"[news] RSS fetch failed ({url[:60]}): {e}")
        return []


def fetch_yahoo_rss(query: str, max_items: int = 20) -> list[dict]:
    """Yahoo ニュース RSS"""
    encoded = requests.utils.quote(query)
    url = f"https://news.yahoo.co.jp/rss/search/topstories?p={encoded}&ei=UTF-8"
    key = f"yahoo:{hashlib.md5(query.encode()).hexdigest()}"
    return _fetch_rss(url, key, max_items)


def fetch_google_news_rss(query: str, max_items: int = 20) -> list[dict]:
    """Google News RSS (日本語)"""
    encoded = requests.utils.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ja&gl=JP&ceid=JP:ja"
    key = f"google:{hashlib.md5(query.encode()).hexdigest()}"
    return _fetch_rss(url, key, max_items)


def fetch_newsapi(query: str, from_date: str, max_items: int = 10) -> list[dict]:
    """NewsAPI.org (NEWSAPI_KEY が必要)"""
    if not NEWSAPI_KEY:
        return []
    cache_key = f"newsapi:{hashlib.md5((query+from_date).encode()).hexdigest()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q":        query,
                "from":     from_date,
                "language": "ja",
                "sortBy":   "publishedAt",
                "pageSize": max_items,
                "apiKey":   NEWSAPI_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        items = []
        for a in data.get("articles", [])[:max_items]:
            items.append({
                "title":       a.get("title",       ""),
                "description": a.get("description", "") or "",
                "pubDate":     a.get("publishedAt", ""),
                "link":        a.get("url",         ""),
            })
        _cache_set(cache_key, items)
        return items
    except Exception as e:
        print(f"[news] NewsAPI failed: {e}")
        return []


# ── 日付パーサー ──────────────────────────────────────────────────────────

def parse_pubdate(s: str) -> Optional[datetime]:
    if not s:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


# ── LLM センチメント ──────────────────────────────────────────────────────

def llm_score(titles: list[str], code: str) -> float:
    """gpt-4o-mini でバッチセンチメント分析"""
    if not titles or not OPENAI_API_KEY:
        return 0.0
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        headlines = "\n".join(f"- {t}" for t in titles[:12])
        prompt = (
            f"以下は銘柄{code}に関するニュースヘッドラインです。\n"
            "株価への翌日の影響を -1.0（非常にネガティブ）から +1.0（非常にポジティブ）の\n"
            "浮動小数点数のみで評価してください。理由は不要です。\n\n"
            f"{headlines}"
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0,
        )
        val = float(resp.choices[0].message.content.strip())
        return max(-1.0, min(1.0, val))
    except Exception as e:
        print(f"[news] LLM sentiment failed: {e}")
        return 0.0


# ── 記事の収集（蓄積用） ───────────────────────────────────────────────────

def collect_raw_articles(code: str, company_name: str, lookback_days: int = 3) -> list[dict]:
    """
    銘柄に関する記事を取得して返す（source つき・重複除去済み）。
    学習用の特徴量は、ここで取った記事を DB に蓄積して作る（news_store.py / collect_news.py）。
    """
    from_str = (datetime.now(tz=JST) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    sources = [
        ("yahoo",   fetch_yahoo_rss(company_name, max_items=20)),
        ("yahoo",   fetch_yahoo_rss(code[:4], max_items=10)),
        ("google",  fetch_google_news_rss(company_name, max_items=20)),
        ("newsapi", fetch_newsapi(company_name, from_date=from_str, max_items=10)),
    ]
    seen: set[str] = set()
    items: list[dict] = []
    for source, fetched in sources:
        for it in fetched:
            key = (it.get("link") or it.get("title") or "")[:200]
            if key and key not in seen:
                seen.add(key)
                items.append({**it, "source": source})
    return items


# ── メイン: 銘柄ごとのセンチメント ───────────────────────────────────────

def get_news_sentiment(
    code: str,
    company_name: str,
    target_date: Optional[datetime] = None,
    lookback_days: int = 3,
) -> dict:
    """
    指定銘柄の「いま」のニュースセンチメントを返す（画面表示・動作確認用）。

    ※ 学習用の特徴量には使わない。過去の日付に今日の値を付けるとリークになるため、
      学習用は news_store.build_point_in_time_features（蓄積した記事から時点ごとに作る）を使う。

    Returns:
        {
            "news_sentiment":        float,  # 総合スコア [-1, +1]
            "news_pos_count":        int,
            "news_neg_count":        int,
            "news_article_count":    int,
            "news_urgency":          float,  # 速報ワード含有率 [0, 1]
        }
    """
    if target_date is None:
        target_date = datetime.now(tz=JST)

    cutoff   = target_date - timedelta(days=lookback_days)
    from_str = cutoff.strftime("%Y-%m-%d")

    # ── 記事収集 ──
    all_items: list[dict] = []

    # 1. Yahoo RSS (社名 + コード)
    all_items += fetch_yahoo_rss(company_name, max_items=20)
    all_items += fetch_yahoo_rss(code[:4], max_items=10)

    # 2. Google News RSS
    all_items += fetch_google_news_rss(company_name, max_items=20)

    # 3. NewsAPI（APIキーがある場合）
    all_items += fetch_newsapi(company_name, from_date=from_str, max_items=10)

    # 重複除去（タイトルベース）
    seen_titles: set[str] = set()
    unique_items: list[dict] = []
    for it in all_items:
        key = it["title"][:40]
        if key and key not in seen_titles:
            seen_titles.add(key)
            unique_items.append(it)

    # ── 期間フィルタ ──
    recent: list[dict] = []
    for item in unique_items:
        pub = parse_pubdate(item.get("pubDate", ""))
        if pub is None:
            recent.append(item)  # 日時不明は含める
            continue
        try:
            pub_jst = pub.astimezone(JST)
        except Exception:
            pub_jst = pub.replace(tzinfo=JST)
        cutoff_aware = cutoff.astimezone(JST) if cutoff.tzinfo else cutoff.replace(tzinfo=JST)
        target_aware = target_date.astimezone(JST) if target_date.tzinfo else target_date.replace(tzinfo=JST)
        if cutoff_aware <= pub_jst <= target_aware:
            recent.append(item)

    if not recent:
        return {
            "news_sentiment":     0.0,
            "news_pos_count":     0,
            "news_neg_count":     0,
            "news_article_count": 0,
            "news_urgency":       0.0,
        }

    # ── スコアリング ──
    texts  = [it["title"] + " " + it.get("description", "") for it in recent]
    scores = [weighted_score(t) for t in texts]
    urgencies = [urgency_score(it["title"]) for it in recent]

    if USE_LLM_SENTIMENT:
        titles = [it["title"] for it in recent]
        sentiment = llm_score(titles, code)
    else:
        # 記事数で正規化。スコアが大きい記事に重み付け
        abs_scores = [abs(s) for s in scores]
        total_w    = sum(abs_scores) + 1e-9
        sentiment  = sum(s * abs(s) for s in scores) / total_w  # 強いシグナルに重み

    pos_count = sum(1 for s in scores if s > 0.05)
    neg_count = sum(1 for s in scores if s < -0.05)
    avg_urgency = sum(urgencies) / len(urgencies) if urgencies else 0.0

    return {
        "news_sentiment":     round(float(sentiment), 4),
        "news_pos_count":     pos_count,
        "news_neg_count":     neg_count,
        "news_article_count": len(recent),
        "news_urgency":       round(avg_urgency, 4),
    }


def get_sector_sentiment(
    sector_code: str,
    target_date: Optional[datetime] = None,
    lookback_days: int = 2,
) -> float:
    """
    セクター全体のニュースセンチメントスコアを返す。
    セクターキーワードで Google News を検索してスコアリング。
    """
    keywords = SECTOR_KEYWORDS.get(sector_code, [])
    if not keywords:
        return 0.0

    if target_date is None:
        target_date = datetime.now(tz=JST)

    cutoff = target_date - timedelta(days=lookback_days)
    all_items: list[dict] = []
    for kw in keywords[:2]:  # 最大2ワードで検索
        all_items += fetch_google_news_rss(kw, max_items=15)

    if not all_items:
        return 0.0

    scores = [weighted_score(it["title"] + " " + it.get("description", "")) for it in all_items]
    valid  = [s for s in scores if s != 0.0]
    return round(sum(valid) / len(valid), 4) if valid else 0.0


def build_news_features_df(
    codes_names: list[tuple[str, str]],
    sector_map: Optional[dict[str, str]] = None,  # code → sector_code
    target_date: Optional[datetime] = None,
    sleep_sec: float = 0.3,
) -> pd.DataFrame:
    """
    複数銘柄のニュースセンチメント特徴量 DataFrame を返す。

    columns:
      Code, news_sentiment, news_pos_count, news_neg_count,
      news_article_count, news_urgency, news_sector_sentiment
    """
    sector_cache: dict[str, float] = {}
    rows = []

    for code, name in codes_names:
        result = get_news_sentiment(code, name, target_date)
        result["Code"] = code

        # セクターセンチメント
        sec_code = (sector_map or {}).get(code, "")
        if sec_code:
            if sec_code not in sector_cache:
                sector_cache[sec_code] = get_sector_sentiment(sec_code, target_date)
            result["news_sector_sentiment"] = sector_cache[sec_code]
        else:
            result["news_sector_sentiment"] = 0.0

        rows.append(result)
        time.sleep(sleep_sec)

    cols = [
        "Code", "news_sentiment", "news_pos_count", "news_neg_count",
        "news_article_count", "news_urgency", "news_sector_sentiment",
    ]
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = 0.0
    return df[cols]


# ── スタンドアロンテスト ─────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ニュースセンチメント単体テスト")
    parser.add_argument("--code",    default="7203",   help="銘柄コード（4桁）")
    parser.add_argument("--name",    default="トヨタ", help="会社名")
    parser.add_argument("--sector",  default="0050",   help="セクターコード")
    parser.add_argument("--days",    default=3,        type=int, help="遡り日数")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"  銘柄: {args.code} {args.name}  |  sector: {args.sector}")
    print(f"{'='*50}")

    result = get_news_sentiment(args.code, args.name, lookback_days=args.days)
    for k, v in result.items():
        print(f"  {k:<26}: {v}")

    sec_score = get_sector_sentiment(args.sector)
    print(f"  {'news_sector_sentiment':<26}: {sec_score}")

    print(f"\nキャッシュエントリ数: {len(_CACHE)}")
