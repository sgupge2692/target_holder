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
from app.notifications import send_email, render_daily_signal_email, make_unsubscribe_url

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://stock:stock@localhost:5432/stockdb")
SITE_URL = os.getenv("NEXT_PUBLIC_SITE_URL", "https://kabumi.app")
# 1送信ごとのウェイト（レート制限対策: 0.1秒）
SEND_INTERVAL = float(os.getenv("EMAIL_SEND_INTERVAL", "0.1"))
# 1ユーザーへのリトライ回数
MAX_RETRIES = int(os.getenv("EMAIL_MAX_RETRIES", "3"))


STALE_AFTER_DAYS = 4          # 最新シグナルがこれより古ければ配信しない（連休明け等に古い情報を送らない）
ACCURACY_WINDOW_DAYS = 30
MIN_ACCURACY_SAMPLES = 30     # 母数が少ない的中率は載せない


def _to_date(value) -> date | None:
    """DB の日付（date / datetime / 文字列）を date にそろえる"""
    if value is None:
        return None
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    if hasattr(value, "date"):
        return value.date()
    return value


async def fetch_today_signals(session: AsyncSession, limit: int = 50) -> list[dict]:
    """
    最新日の「市場平均を上回る」シグナル（UP）を、確度の高い順に取得する。
    （列名は db/init.sql の実スキーマ: "Code" / "Date" / up_probability）
    """
    latest = _to_date((await session.execute(text('SELECT MAX("Date") FROM predictions'))).scalar())
    if latest is None:
        return []

    result = await session.execute(
        text("""
            SELECT p."Code" AS code, ls.company_name, p.signal, p.up_probability, p."Date" AS pred_date
            FROM predictions p
            LEFT JOIN listed_stocks ls ON ls.code = p."Code"
            WHERE p."Date" = :d AND p.signal = 'UP'
            ORDER BY p.up_probability DESC
            LIMIT :limit
        """),
        {"d": latest, "limit": limit},
    )
    return [
        {
            "code": r.code,
            "company_name": r.company_name or r.code,
            "signal": r.signal,
            "probability_pct": float(r.up_probability) * 100 if r.up_probability is not None else 0.0,
            "pred_date": str(_to_date(r.pred_date)),
        }
        for r in result.fetchall()
    ]


async def fetch_accuracy(session: AsyncSession) -> dict:
    """直近30日の UP シグナルの的中率（対市場の判定 is_correct）。母数が少なければ空。"""
    since = date.today() - timedelta(days=ACCURACY_WINDOW_DAYS)
    row = (await session.execute(
        text("""
            SELECT SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS hits, COUNT(*) AS total
            FROM predictions
            WHERE signal = 'UP' AND is_correct IS NOT NULL AND "Date" >= :since
        """),
        {"since": since},
    )).fetchone()
    if not row or not row.total or row.total < MIN_ACCURACY_SAMPLES:
        return {}
    return {"UP": {"accuracy_pct": float(row.hits or 0) * 100.0 / row.total, "total": int(row.total)}}


async def fetch_watch_changes(session: AsyncSession, signal_date: date) -> dict[int, list[dict]]:
    """
    ウォッチリストの銘柄のうち、前回の予測からシグナルが変わったもの（UP/DOWN/NEUTRAL の入れ替わり）。
    Returns: {user_id: [{"code","company_name","prev_signal","signal","probability_pct"}]}
    """
    rows = await session.execute(
        text("""
            SELECT w.user_id, w.code,
                   COALESCE(w.company_name, ls.company_name) AS company_name,
                   p.signal, p.up_probability,
                   (SELECT p2.signal FROM predictions p2
                     WHERE p2."Code" = p."Code" AND p2."Date" < p."Date"
                     ORDER BY p2."Date" DESC LIMIT 1) AS prev_signal
            FROM watchlist w
            JOIN predictions p ON p."Code" = w.code
            LEFT JOIN listed_stocks ls ON ls.code = w.code
            WHERE p."Date" = :d
              AND p.id IN (SELECT MAX(id) FROM predictions WHERE "Date" = :d GROUP BY "Code")
            ORDER BY w.user_id, w.code
        """),
        {"d": signal_date},
    )
    changes: dict[int, list[dict]] = {}
    for r in rows.fetchall():
        if r.prev_signal is None or r.prev_signal == r.signal:
            continue
        if r.signal == "NEUTRAL" and r.prev_signal == "NEUTRAL":
            continue
        changes.setdefault(r.user_id, []).append({
            "code": r.code,
            "company_name": r.company_name or r.code,
            "prev_signal": r.prev_signal,
            "signal": r.signal,
            "probability_pct": float(r.up_probability) * 100,
        })
    return changes


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


async def main(
    dry_run: bool = False,
    user_limit: int | None = None,
    test_email: str | None = None,
) -> None:
    today_str = date.today().strftime("%Y年%m月%d日")
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with AsyncSession(engine) as session:
        signals = await fetch_today_signals(session, limit=50)
        accuracy_info = await fetch_accuracy(session)
        signal_date = _to_date(signals[0]["pred_date"]) if signals else None
        watch_changes = await fetch_watch_changes(session, signal_date) if signal_date else {}
        if test_email:
            # テスト送信: 指定アドレスに1通だけ送る
            result = await session.execute(
                select(User).where(User.email == test_email)
            )
            user_obj = result.scalar_one_or_none()
            subscribers = [user_obj] if user_obj else []
            if not user_obj:
                logger.warning(f"テスト対象ユーザーが見つかりません: {test_email}")
        else:
            subscribers = await get_alert_subscribers(session)

    await engine.dispose()

    up_accuracy = accuracy_info.get("UP", {}).get("accuracy_pct")

    if not signals:
        logger.info("配信できるシグナルがありません。終了します。")
        return

    signal_date_str = signals[0].get("pred_date", today_str)
    age = (date.today() - signal_date).days if signal_date else 0
    if age > STALE_AFTER_DAYS:
        logger.warning(f"最新シグナルが {signal_date_str}（{age}日前）で古いため、配信をスキップします。")
        return
    subject = f"📈 {signal_date_str}のAIシグナル — 市場を上回ると予測 {len(signals)}銘柄"
    if test_email:
        subject = f"[テスト] {subject}"

    targets = subscribers[:user_limit] if user_limit else subscribers
    logger.info(
        f"シグナル {len(signals)} 件 / 配信対象 {len(targets)} 名"
        f"{' [DRY RUN]' if dry_run else ''}"
        f"{' [TEST]' if test_email else ''}"
    )

    sent = failed = skipped = 0
    for user in targets:
        unsub_url = make_unsubscribe_url(user.id, user.email, SITE_URL)
        user_changes = watch_changes.get(user.id, [])
        html = render_daily_signal_email(
            date=signal_date_str,
            signals=signals,
            accuracy_pct=up_accuracy,
            site_url=SITE_URL,
            unsubscribe_url=unsub_url,
            watch_changes=user_changes,
            accuracy_n=accuracy_info.get("UP", {}).get("total"),
        )

        if dry_run:
            logger.info(f"  [DRY RUN] → {user.email}")
            logger.info(f"    unsubscribe_url: {unsub_url}")
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
    parser.add_argument(
        "--test-email", metavar="EMAIL", default=None,
        help="指定アドレスに1通だけテスト送信（Proフラグ不要）"
    )
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run, user_limit=args.limit, test_email=args.test_email))
