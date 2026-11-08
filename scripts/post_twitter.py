#!/usr/bin/env python3
"""
X(Twitter) 自動投稿スクリプト — 日次シグナル（市場超過確率の上位銘柄）を投稿

cron: 50 18 * * 1-5  (send_daily_signals.py の直後)

必要な環境変数 (Twitter API v2 / OAuth 1.0a):
  TWITTER_API_KEY
  TWITTER_API_SECRET
  TWITTER_ACCESS_TOKEN
  TWITTER_ACCESS_TOKEN_SECRET

実行方法:
  python scripts/post_twitter.py --dry-run   # 投稿せず、文面だけ確認する
  python scripts/post_twitter.py
  docker compose run --rm backend python /scripts/post_twitter.py

終了コード: 0=成功またはスキップ（シグナル無し・古いデータ・認証情報なし）、1=失敗
（cron のログで気づけるよう、失敗は握りつぶさない）

投稿方針:
  - 無料プランで見られる件数（上位 FREE_SIGNAL_LIMIT 件）だけを載せる。続きはサービスで。
  - モデルは「翌日、市場平均を上回るか」を予測している。文面もそれに合わせる。
  - 的中率は対市場の判定（predictions.is_correct）で、母数(n)を併記する。
  - 売買の推奨・勧誘に見えないよう、免責を必ず付ける。
"""
import argparse
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://stock:stock@localhost:5432/stockdb")
SITE_URL = os.getenv("NEXT_PUBLIC_SITE_URL", "https://kabumi.app")

MAX_STOCKS_IN_TWEET = 3        # 無料プランの閲覧上限（backend/app/routers/signals.py の FREE_SIGNAL_LIMIT）に合わせる
STALE_AFTER_DAYS = 4           # 最新シグナルがこれより古ければ投稿しない（連休明け等の古い情報を出さない）
ACCURACY_WINDOW_DAYS = 30
MIN_ACCURACY_SAMPLES = 30      # 母数が少ない的中率は載せない（見せかけの精度を避ける）
TWEET_LIMIT = 280              # X の上限（重み付き。日本語は 1 文字 = 2）
URL_WEIGHT = 23                # X は URL を一律 23 として数える

DISCLAIMER = "※情報提供であり投資助言・売買の推奨ではありません。"
HASHTAGS = "#株式投資 #株価予測"


# ────────────────────────────────────────────────────────────────
# 文字数（X の重み付きカウント）
# ────────────────────────────────────────────────────────────────

_URL_RE = re.compile(r"https?://\S+")


def _char_weight(ch: str) -> int:
    """X の仕様: 半角英数・ラテン文字などは 1、日本語など CJK・絵文字は 2。"""
    cp = ord(ch)
    if (
        cp <= 0x10FF
        or 0x2000 <= cp <= 0x200D
        or 0x2010 <= cp <= 0x201F
        or 0x2032 <= cp <= 0x2037
    ):
        return 1
    return 2


def tweet_weight(text: str) -> int:
    """ツイートの重み付き文字数（URL は一律 23）。"""
    urls = _URL_RE.findall(text)
    without_urls = _URL_RE.sub("", text)
    return sum(_char_weight(c) for c in without_urls) + URL_WEIGHT * len(urls)


# ────────────────────────────────────────────────────────────────
# 文面
# ────────────────────────────────────────────────────────────────

def build_tweet(
    signals: list[dict],
    accuracy: dict | None,
    today_str: str,
    site_url: str = SITE_URL,
) -> str:
    """
    ツイート本文を作る。上限を超える場合は、掲載銘柄を減らして収める。

    signals : [{"code", "name", "prob"(%)}]  確度の高い順
    accuracy: {"rate"(%), "n"} または None
    """
    for count in range(len(signals), 0, -1):
        lines = [f"📊 {today_str} AIシグナル", "翌日に市場平均を上回ると予測した上位銘柄", ""]
        for s in signals[:count]:
            lines.append(f"{s['code']} {s['name']} 超過確率{s['prob']:.0f}%")
        if accuracy:
            lines.append("")
            lines.append(f"直近{ACCURACY_WINDOW_DAYS}日 的中率(対市場) {accuracy['rate']:.1f}% (n={accuracy['n']})")
        lines += ["", f"全シグナルはこちら ▶ {site_url}", DISCLAIMER, HASHTAGS]
        text = "\n".join(lines)
        if tweet_weight(text) <= TWEET_LIMIT:
            return text

    raise ValueError("ツイートが上限を超えます（銘柄を 1 件にしても収まりません）")


# ────────────────────────────────────────────────────────────────
# DB
# ────────────────────────────────────────────────────────────────

async def fetch_signals(today: date | None = None) -> tuple[list[dict], dict | None, date | None]:
    """
    最新日のシグナル上位（市場超過確率が高い順）と、直近の的中率を取得する。

    Returns:
        (signals, accuracy, signal_date)  signal_date はシグナルの基準日（無ければ None）
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    today = today or date.today()
    engine = create_async_engine(DATABASE_URL, echo=False)
    try:
        async with AsyncSession(engine) as session:
            latest = (await session.execute(text('SELECT MAX("Date") FROM predictions'))).scalar()
            if latest is None:
                return [], None, None
            if isinstance(latest, str):                    # SQLite 等では文字列で返る
                latest = date.fromisoformat(latest[:10])
            elif hasattr(latest, "date"):
                latest = latest.date()

            rows = (await session.execute(
                text("""
                    SELECT p."Code" AS code, ls.company_name, p.up_probability
                    FROM predictions p
                    LEFT JOIN listed_stocks ls ON ls.code = p."Code"
                    WHERE p."Date" = :d AND p.signal = 'UP'
                    ORDER BY p.up_probability DESC
                    LIMIT :limit
                """),
                {"d": latest, "limit": MAX_STOCKS_IN_TWEET},
            )).fetchall()

            acc = (await session.execute(
                text("""
                    SELECT COUNT(*) FILTER (WHERE is_correct) AS hits, COUNT(*) AS n
                    FROM predictions
                    WHERE signal = 'UP' AND is_correct IS NOT NULL AND "Date" >= :since
                """),
                {"since": today - timedelta(days=ACCURACY_WINDOW_DAYS)},
            )).fetchone()
    finally:
        await engine.dispose()

    signals = [
        {
            "code": r.code,
            "name": (r.company_name or r.code)[:6],
            "prob": float(r.up_probability) * 100,
        }
        for r in rows
    ]
    accuracy = None
    if acc and acc.n and acc.n >= MIN_ACCURACY_SAMPLES:
        accuracy = {"rate": acc.hits * 100.0 / acc.n, "n": int(acc.n)}
    return signals, accuracy, latest


# ────────────────────────────────────────────────────────────────
# X API
# ────────────────────────────────────────────────────────────────

def _oauth1_header(method: str, url: str, params: dict) -> str:
    """OAuth 1.0a 署名ヘッダーを生成"""
    oauth_params = {
        "oauth_consumer_key": TWITTER_API_KEY,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": TWITTER_ACCESS_TOKEN,
        "oauth_version": "1.0",
    }
    all_params = {**params, **oauth_params}
    sorted_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(all_params.items())
    )
    base_str = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(sorted_params, safe=""),
    ])
    signing_key = (
        f"{urllib.parse.quote(TWITTER_API_SECRET, safe='')}&"
        f"{urllib.parse.quote(TWITTER_ACCESS_TOKEN_SECRET, safe='')}"
    )
    sig = base64.b64encode(
        hmac.new(signing_key.encode(), base_str.encode(), hashlib.sha1).digest()
    ).decode()
    oauth_params["oauth_signature"] = sig
    header_parts = ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(str(v), safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {header_parts}"


def credentials_set() -> bool:
    return all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET])


def post_tweet(text: str) -> bool:
    """ツイート投稿 (Twitter API v2)。成功で True。"""
    url = "https://api.twitter.com/2/tweets"
    req = urllib.request.Request(
        url,
        data=json.dumps({"text": text}).encode(),
        headers={
            "Authorization": _oauth1_header("POST", url, {}),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            logger.info(f"Tweet posted: https://twitter.com/i/web/status/{body.get('data', {}).get('id')}")
            return True
    except urllib.error.HTTPError as e:
        logger.error(f"Twitter API error: {e.code} {e.read().decode()}")
    except Exception as e:
        logger.error(f"Tweet failed: {e}")
    return False


# ────────────────────────────────────────────────────────────────
# エントリポイント
# ────────────────────────────────────────────────────────────────

async def main(dry_run: bool = False) -> int:
    logger.info("シグナル取得中...")
    try:
        signals, accuracy, signal_date = await fetch_signals()
    except Exception as e:
        logger.error(f"DB取得失敗: {e}")
        return 1

    if not signals or signal_date is None:
        logger.info("シグナルなし。ツイートスキップ。")
        return 0

    age = (date.today() - signal_date).days
    if age > STALE_AFTER_DAYS:
        logger.warning(f"最新シグナルが {signal_date}（{age}日前）で古いため、ツイートスキップ。")
        return 0

    tweet = build_tweet(signals, accuracy, signal_date.strftime("%m/%d"))
    logger.info(f"ツイート内容 (重み {tweet_weight(tweet)}/{TWEET_LIMIT}):\n{tweet}")

    if dry_run:
        logger.info("--dry-run のため投稿しません。")
        return 0
    if not credentials_set():
        logger.warning("Twitter credentials not set; tweet skipped")
        return 0

    if post_tweet(tweet):
        logger.info("ツイート完了 ✓")
        return 0
    logger.error("ツイート失敗 ✗")
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="日次シグナルを X に投稿する")
    parser.add_argument("--dry-run", action="store_true", help="投稿せず文面だけ表示する")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(dry_run=args.dry_run)))
