"""
ニュースセンチメント特徴量生成モジュール

Yahoo Finance Japan の RSS フィードから銘柄関連ニュースを取得し、
辞書ベースのポジティブ/ネガティブスコアを計算する。

使用方法:
  単体テスト: python pipeline/news_sentiment.py --code 7203
  feature_engineering.py から import して使用
"""
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

JST = timezone(timedelta(hours=9))

# ── ポジティブ辞書（金融ドメイン向け） ────────────────────────────────
POSITIVE_WORDS = [
    "上昇", "増収", "増益", "最高益", "黒字", "上方修正", "好調", "好業績", "買い",
    "強気", "急騰", "高値", "上方", "拡大", "増加", "改善", "成長", "躍進", "好転",
    "回復", "反発", "値上がり", "値上がり", "増配", "特需", "受注", "新高値",
    "過去最高", "大幅増", "急増", "利益率向上", "目標株価引き上げ", "格上げ",
    "新製品", "新サービス", "提携", "買収", "合併", "出資", "業績予想上方",
]

NEGATIVE_WORDS = [
    "下落", "減収", "減益", "最終赤字", "赤字", "下方修正", "不調", "悪化", "売り",
    "弱気", "急落", "安値", "下方", "縮小", "減少", "悪化", "低迷", "後退", "悪転",
    "不振", "反落", "値下がり", "減配", "無配", "リコール", "訴訟", "行政処分",
    "業績予想下方", "損失", "損失計上", "一時損失", "格下げ", "目標株価引き下げ",
    "倒産", "民事再生", "解雇", "リストラ", "不正", "不祥事", "調査",
]

# OpenAI を使った高精度センチメント（オプション）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
USE_LLM_SENTIMENT = bool(OPENAI_API_KEY) and os.getenv("NEWS_USE_LLM", "false").lower() == "true"


# ── RSS フェッチ ─────────────────────────────────────────────────────

def fetch_yahoo_rss(query: str, max_items: int = 20) -> list[dict]:
    """Yahoo Finance Japan の RSS からニュースを取得"""
    url = f"https://news.yahoo.co.jp/rss/search/topstories?p={requests.utils.quote(query)}&ei=UTF-8"
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = []
        for item in root.iter("item"):
            title = item.findtext("title") or ""
            desc  = item.findtext("description") or ""
            pub   = item.findtext("pubDate") or ""
            items.append({"title": title, "description": desc, "pubDate": pub})
            if len(items) >= max_items:
                break
        return items
    except Exception as e:
        print(f"RSS fetch failed for '{query}': {e}")
        return []


def parse_pubdate(s: str) -> Optional[datetime]:
    """RSS の pubDate を datetime に変換"""
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


# ── 辞書ベース スコア計算 ────────────────────────────────────────────

def dict_score(text: str) -> float:
    """
    ポジティブ/ネガティブ語の出現数から [-1, +1] のスコアを返す。
    スコア = (pos - neg) / (pos + neg + 1)
    """
    pos = sum(1 for w in POSITIVE_WORDS if w in text)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text)
    return (pos - neg) / (pos + neg + 1)


def llm_score(titles: list[str], code: str) -> float:
    """gpt-4o-mini でバッチセンチメント分析（USE_LLM_SENTIMENT=true の時のみ使用）"""
    if not titles:
        return 0.0
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        headlines = "\n".join(f"- {t}" for t in titles[:10])
        prompt = f"""以下は銘柄{code}に関するニュースヘッドラインです。
株価への影響を -1.0（非常にネガティブ）から +1.0（非常にポジティブ）の
浮動小数点数で評価してください。数値のみ返答してください。

{headlines}"""
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0,
        )
        return float(resp.choices[0].message.content.strip())
    except Exception as e:
        print(f"LLM sentiment failed: {e}")
        return 0.0


# ── メイン: 銘柄ごとのセンチメント取得 ──────────────────────────────

def get_news_sentiment(
    code: str,
    company_name: str,
    target_date: Optional[datetime] = None,
    lookback_days: int = 3,
) -> dict:
    """
    指定銘柄のニュースセンチメントスコアを返す。

    Returns:
        {
            "news_sentiment":      float,  # メインスコア [-1, +1]
            "news_pos_count":      int,    # ポジティブ記事数
            "news_neg_count":      int,    # ネガティブ記事数
            "news_article_count":  int,    # 取得記事総数
        }
    """
    if target_date is None:
        target_date = datetime.now(tz=JST)

    cutoff = target_date - timedelta(days=lookback_days)

    # 銘柄コード（4桁）と社名で検索
    items = fetch_yahoo_rss(company_name, max_items=20)
    # コードでも補完検索
    code_4 = code[:4]
    items += fetch_yahoo_rss(code_4, max_items=10)

    # 期間フィルタ
    recent = []
    for item in items:
        pub = parse_pubdate(item.get("pubDate", ""))
        if pub:
            pub_jst = pub.astimezone(JST).replace(tzinfo=None)
            target_naive = target_date.replace(tzinfo=None)
            cutoff_naive = cutoff.replace(tzinfo=None)
            if cutoff_naive <= pub_jst <= target_naive:
                recent.append(item)
        else:
            recent.append(item)  # 日時不明は含める

    if not recent:
        return {
            "news_sentiment":     0.0,
            "news_pos_count":     0,
            "news_neg_count":     0,
            "news_article_count": 0,
        }

    titles = [it["title"] for it in recent]
    scores = [dict_score(it["title"] + " " + it["description"]) for it in recent]

    if USE_LLM_SENTIMENT:
        sentiment = llm_score(titles, code)
    else:
        sentiment = sum(scores) / len(scores) if scores else 0.0

    pos_count = sum(1 for s in scores if s > 0.05)
    neg_count = sum(1 for s in scores if s < -0.05)

    return {
        "news_sentiment":     round(float(sentiment), 4),
        "news_pos_count":     pos_count,
        "news_neg_count":     neg_count,
        "news_article_count": len(recent),
    }


def build_news_features_df(
    codes_names: list[tuple[str, str]],
    target_date: Optional[datetime] = None,
    sleep_sec: float = 0.5,
) -> pd.DataFrame:
    """
    複数銘柄のニュースセンチメント特徴量 DataFrame を返す。
    feature_engineering.py の add_relative_features の後に merge して使用。

    columns: Code, news_sentiment, news_pos_count, news_neg_count, news_article_count
    """
    rows = []
    for code, name in codes_names:
        result = get_news_sentiment(code, name, target_date)
        result["Code"] = code
        rows.append(result)
        time.sleep(sleep_sec)  # レートリミット対策

    return pd.DataFrame(rows)[
        ["Code", "news_sentiment", "news_pos_count", "news_neg_count", "news_article_count"]
    ]


# ── スタンドアロンテスト ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", default="7203", help="銘柄コード（4桁）")
    parser.add_argument("--name", default="トヨタ",  help="会社名")
    args = parser.parse_args()

    result = get_news_sentiment(args.code, args.name)
    print(f"\n=== {args.code} {args.name} のニュースセンチメント ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
