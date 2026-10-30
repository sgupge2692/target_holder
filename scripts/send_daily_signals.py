#!/usr/bin/env python3
"""
毎日のシグナルメール配信スクリプト
cron: 45 18 * * 1-5  (東証引け後 18:45 JST に実行)

実行方法:
  docker compose run --rm backend python /scripts/send_daily_signals.py
  または
  python scripts/send_daily_signals.py (ローカル、.env ファイル読み込み)

オプション:
  --dry-run   DBから読み込むが実際のメールは送信しない
  --limit N   送信件数上限（デフォルト: 全件）
"""
import sys
import os
import asyncio
import logging
import argparse
import time
from datetime import date, timedelta

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select, text
from app.models import User
from app.notifications import send_email, render_daily_signal_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://stock:stock@localhost:5432/stockdb")
SITE_URL = os.getenv("NEXT_PUBLIC_SITE_URL", "https://stock-intelligence.app")
# 1送信ごとのウェイト（レート制限対策: 0.1秒）
SEND_INTERVAL = float(os.getenv("EMAIL_SEND_INTERVAL", "0.1"))
# 1ユーザーへのリトライ回数
MAX_RETRIES = int(os.getenv("EMAIL_MAX_RETRIES", "3"))


async def fetch_today_signals(session: AsyncSession, limit: int = 50) -> list[dict]:
    """今日の予測シグナルを取得。なければ直近営業日のシグナルを取得。"""
    today = date.today().isoformat()
    result = await session.execute(
        text("""
            SELECT p.code, ls.company_name, p.signal, p.probability,
                   p.predicted_at::date AS pred_date
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

    # 本日分がなければ直近7営業日以内を検索
    if not rows:
        logger.info("本日のシグナルなし。直近7日以内のデータを検索します。")
        cutoff = (date.today() - timedelta(days=7)).isoformat()
        result = await session.execute(
            text("""
                SELECT p.code, ls.company_name, p.signal, p.probability,
                       p.predicted_at::date AS pred_date
                FROM predictions p
                LEFT JOIN listed_stocks ls ON p.code = ls.code
                WHERE p.predicted_at::date >= :cutoff
                  AND p.signal = 'UP'
                ORDER BY p.predicted_at DESC, p.probability DESC
                LIMIT :limit
            """),
            {"cutoff": cutoff, "limit": limit},
        )
        rows = result.fetchall()

    return [
        {
            "code": r.code,
            "company_name": r.company_name or r.code,
            "signal": r.signal,
            "probability_pct": float(r.probability) * 100 if r.probability else 0,
            "pred_date": str(r.pred_date),
        }
        for r in rows
    ]


async def fetch_accuracy(session: AsyncSession) -> dict:
    """直近30日の UP/DOWN 精度を取得"""
    result = await session.execute(
        text("""
            SELECT
                signal,
                COUNT(*) FILTER (WHERE actual_return > 0) * 100.0 / NULLIF(COUNT(*), 0) AS acc,
                AVG(actual_return) * 100 AS avg_ret,
                COUNT(*) AS total
            FROM predictions
            WHERE actual_return IS NOT NULL
              AND predicted_at >= NOW() - INTERVAL '30 days'
            GROUP BY signal
        """)
    )
    rows = result.fetchall()
    info: dict = {}
    for r in rows:
        info[r.signal] = {
            "accuracy_pct": float(r.acc) if r.acc else None,
            "avg_return_pct": float(r.avg_ret) if r.avg_ret else None,
            "total": r.total,
        }
    return info


async def get_alert_subscribers(session: AsyncSession) -> list[User]:
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


def _send_with_retry(to: str, subject: str, html: str, retries: int = MAX_RETRIES) -> bool:
    """リトライ付きメール送信"""
    for attempt in range(1, retries + 1):
        ok = send_email(to=to, subject=subject, html=html)
        if ok:
            return True
        if attempt < retries:
            wait = 2 ** attempt  # 指数バックオフ: 2, 4 秒
            logger.warning(f"  送信失敗 {attempt}/{retries}回目: {to} — {wait}秒後にリトライ")
            time.sleep(wait)
    return False


async def main(dry_run: bool = False, user_limit: int | None = None) -> None:
    today_str = date.today().strftime("%Y年%m月%d日")
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with AsyncSession(engine) as session:
        signals = await fetch_today_signals(session, limit=50)
        accuracy_info = await fetch_accuracy(session)
        subscribers = await get_alert_subscribers(session)

    await engine.dispose()

    up_accuracy = accuracy_info.get("UP", {}).get("accuracy_pct")

    if not signals:
        logger.info(f"配信できるシグナルがありません。終了します。")
        return

    signal_date_str = signals[0].get("pred_date", today_str)
    subject = f"📈 {signal_date_str}のAIシグナル — UP候補 {len(signals)}銘柄"

    targets = subscribers[:user_limit] if user_limit else subscribers
    logger.info(
        f"シグナル {len(signals)} 件 / 配信対象 {len(targets)} 名"
        f"{' [DRY RUN]' if dry_run else ''}"
    )

    sent = failed = skipped = 0
    for user in targets:
        html = render_daily_signal_email(
            date=signal_date_str,
            signals=signals,
            accuracy_pct=up_accuracy,
            site_url=SITE_URL,
        )

        if dry_run:
            logger.info(f"  [DRY RUN] → {user.email}")
            skipped += 1
            continue

        ok = _send_with_retry(to=user.email, subject=subject, html=html)
        if ok:
            sent += 1
            logger.info(f"  ✓ {user.email}")
        else:
            failed += 1
            logger.error(f"  ✗ {user.email} (全リトライ失敗)")

        # レート制限対策
        if SEND_INTERVAL > 0:
            time.sleep(SEND_INTERVAL)

    logger.info(
        f"完了 — 送信: {sent}, 失敗: {failed}"
        + (f", スキップ(dry): {skipped}" if dry_run else "")
    )
    if failed > 0:
        # CI/CD やモニタリングが失敗を検知できるよう exit code 1
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="日次シグナルメール配信")
    parser.add_argument("--dry-run", action="store_true", help="送信せずログのみ出力")
    parser.add_argument("--limit", type=int, default=None, help="送信ユーザー上限数")
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run, user_limit=args.limit))
