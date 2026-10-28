#!/usr/bin/env python3
"""
毎日のシグナルメール配信スクリプト
cron: 45 18 * * 1-5  (東証引け後 18:45 JST に実行)

実行方法:
  docker compose run --rm backend python /scripts/send_daily_signals.py
  または
  python scripts/send_daily_signals.py (ローカル、.env ファイル読み込み)
"""
import sys
import os
import asyncio
import logging
from datetime import date

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select, text
from app.models import User
from app.notifications import send_email, render_daily_signal_email

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://stock:stock@localhost:5432/stockdb")
SITE_URL = os.getenv("NEXT_PUBLIC_SITE_URL", "https://stock-intelligence.app")


async def fetch_today_signals(session: AsyncSession, limit: int = 50) -> list[dict]:
    """今日の予測シグナルを取得"""
    today = date.today().isoformat()
    result = await session.execute(
        text("""
            SELECT p.code, ls.company_name, p.signal, p.probability,
                   p.predicted_at::date as pred_date
            FROM predictions p
            LEFT JOIN listed_stocks ls ON p.code = ls.code
            WHERE p.predicted_at::date = :today
              AND p.signal = 'UP'
            ORDER BY p.probability DESC
            LIMIT :limit
        """),
        {"today": today, "limit": limit},
    )
    rows = result.fetchall()
    return [
        {
            "code": r.code,
            "company_name": r.company_name or r.code,
            "signal": r.signal,
            "probability_pct": float(r.probability) * 100 if r.probability else 0,
        }
        for r in rows
    ]


async def fetch_accuracy(session: AsyncSession) -> float | None:
    """直近の UP 精度を取得"""
    result = await session.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE actual_return > 0) * 100.0 / NULLIF(COUNT(*), 0) as acc
            FROM predictions
            WHERE signal = 'UP'
              AND actual_return IS NOT NULL
              AND predicted_at >= NOW() - INTERVAL '30 days'
        """)
    )
    row = result.fetchone()
    return float(row.acc) if row and row.acc else None


async def get_pro_subscribers(session: AsyncSession) -> list[User]:
    """メール通知を有効にしている Pro ユーザーを取得"""
    result = await session.execute(
        select(User).where(
            User.plan == "pro",
            User.email_signal_alert == True,
            User.email_unsubscribed == False,
            User.is_active == True,
        )
    )
    return list(result.scalars().all())


async def main():
    today_str = date.today().strftime("%Y年%m月%d日")
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with AsyncSession(engine) as session:
        signals = await fetch_today_signals(session, limit=50)
        accuracy = await fetch_accuracy(session)
        subscribers = await get_pro_subscribers(session)

    await engine.dispose()

    if not signals:
        logger.info(f"本日（{today_str}）のシグナルなし。メール送信スキップ。")
        return

    logger.info(f"シグナル {len(signals)} 件、配信対象 {len(subscribers)} 名")

    sent = 0
    failed = 0
    for user in subscribers:
        html = render_daily_signal_email(
            date=today_str,
            signals=signals,
            accuracy_pct=accuracy,
            site_url=SITE_URL,
        )
        subject = f"📈 {today_str}のAIシグナル — UP候補 {len(signals)}銘柄"
        ok = send_email(to=user.email, subject=subject, html=html)
        if ok:
            sent += 1
            logger.info(f"  ✓ {user.email}")
        else:
            failed += 1
            logger.warning(f"  ✗ {user.email}")

    logger.info(f"送信完了: 成功={sent}, 失敗={failed}")


if __name__ == "__main__":
    asyncio.run(main())
