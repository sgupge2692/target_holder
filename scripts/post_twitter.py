#!/usr/bin/env python3
"""
Twitter/X 自動投稿スクリプト — 日次シグナル結果を投稿
cron: 50 18 * * 1-5  (send_daily_signals.py の直後)

必要な環境変数 (Twitter API v2):
  TWITTER_API_KEY
  TWITTER_API_SECRET
  TWITTER_ACCESS_TOKEN
  TWITTER_ACCESS_TOKEN_SECRET

実行方法:
  python scripts/post_twitter.py
  docker compose run --rm backend python /scripts/post_twitter.py
"""
import sys
import os
import asyncio
import hmac
import hashlib
import base64
import time
import uuid
import urllib.parse
import urllib.request
import json
import logging
from datetime import date

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
SITE_URL = os.getenv("NEXT_PUBLIC_SITE_URL", "https://stock-intelligence.app")
MAX_STOCKS_IN_TWEET = 5


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
    signing_key = f"{urllib.parse.quote(TWITTER_API_SECRET, safe='')}&{urllib.parse.quote(TWITTER_ACCESS_TOKEN_SECRET, safe='')}"
    sig = base64.b64encode(
        hmac.new(signing_key.encode(), base_str.encode(), hashlib.sha1).digest()
    ).decode()
    oauth_params["oauth_signature"] = sig
    header_parts = ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(str(v), safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {header_parts}"


def post_tweet(text: str) -> bool:
    """ツイート投稿 (Twitter API v2)"""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET]):
        logger.warning("Twitter credentials not set; tweet skipped")
        return False

    url = "https://api.twitter.com/2/tweets"
    payload = json.dumps({"text": text}).encode()
    auth_header = _oauth1_header("POST", url, {})

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            tweet_id = body.get("data", {}).get("id")
            logger.info(f"Tweet posted: https://twitter.com/i/web/status/{tweet_id}")
            return True
    except urllib.error.HTTPError as e:
        logger.error(f"Twitter API error: {e.code} {e.read().decode()}")
        return False
    except Exception as e:
        logger.error(f"Tweet failed: {e}")
        return False


async def fetch_signals() -> list[dict]:
    """今日のシグナルをDBから取得"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import text

    today = date.today().isoformat()
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with AsyncSession(engine) as session:
        result = await session.execute(
            text("""
                SELECT p.code, ls.company_name, p.probability,
                       p.signal
                FROM predictions p
                LEFT JOIN listed_stocks ls ON p.code = ls.code
                WHERE p.predicted_at::date = :today
                  AND p.signal = 'UP'
                ORDER BY p.probability DESC
                LIMIT :limit
            """),
            {"today": today, "limit": MAX_STOCKS_IN_TWEET},
        )
        rows = result.fetchall()

        # 直近精度
        acc_result = await session.execute(
            text("""
                SELECT COUNT(*) FILTER (WHERE actual_return > 0) * 100.0 / NULLIF(COUNT(*), 0) as acc
                FROM predictions
                WHERE signal='UP' AND actual_return IS NOT NULL
                  AND predicted_at >= NOW() - INTERVAL '30 days'
            """)
        )
        acc_row = acc_result.fetchone()

    await engine.dispose()

    signals = [
        {
            "code": r.code,
            "name": (r.company_name or r.code)[:6],
            "prob": float(r.probability) * 100 if r.probability else 0,
        }
        for r in rows
    ]
    accuracy = float(acc_row.acc) if acc_row and acc_row.acc else None
    return signals, accuracy


def build_tweet(signals: list[dict], accuracy: float | None, today_str: str) -> str:
    """ツイートテキストを組み立て（280字以内）"""
    lines = [f"📈 {today_str} AIシグナル（翌日UP予測）\n"]
    for s in signals:
        lines.append(f"  {s['code']} {s['name']} — {s['prob']:.0f}%")
    if accuracy:
        lines.append(f"\n直近30日精度: {accuracy:.1f}%")
    lines.append(f"\n▶ {SITE_URL}")
    lines.append("#株式投資 #AI投資 #株価予測")
    return "\n".join(lines)


async def main():
    today_str = date.today().strftime("%m/%d")
    logger.info("シグナル取得中...")

    try:
        signals, accuracy = await fetch_signals()
    except Exception as e:
        logger.error(f"DB取得失敗: {e}")
        return

    if not signals:
        logger.info("本日のシグナルなし。ツイートスキップ。")
        return

    tweet = build_tweet(signals, accuracy, today_str)
    logger.info(f"ツイート内容 ({len(tweet)}文字):\n{tweet}")

    ok = post_tweet(tweet)
    if ok:
        logger.info("ツイート完了 ✓")
    else:
        logger.error("ツイート失敗 ✗")


if __name__ == "__main__":
    asyncio.run(main())
