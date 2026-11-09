"""
ニュース収集スクリプト（毎日 cron で実行して news_articles に蓄積する）

毎営業日、予測の前（18:00 JST より前）に実行する。記事が「使えるようになった時刻」は収集時刻として記録される。
  特徴量は「その日の 18:00 JST までに収集した記事」だけで作る（news_store.py）。GitHub Actions の daily_pipeline.yml に組み込み済み。

  python pipeline/collect_news.py                 # listed_stocks の先頭 NEWS_MAX_STOCKS 銘柄
  python pipeline/collect_news.py --dry-run       # 取得して件数だけ表示（保存しない）
  python pipeline/collect_news.py --codes 72030 99840

環境変数: DATABASE_URL / NEWS_MAX_STOCKS（既定 300） / NEWS_SLEEP_SEC（既定 0.5） / NEWSAPI_KEY（任意）
終了コード: 0=成功、1=全銘柄で取得に失敗（cron のログで気づけるように）
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, text

from news_sentiment import FETCH_STATS, collect_raw_articles
from news_store import article_row, save_articles


def main() -> int:
    parser = argparse.ArgumentParser(description="ニュースを収集して DB に蓄積する")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--codes", nargs="*", help="対象の銘柄コード（省略時は listed_stocks の先頭から）")
    args = parser.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
    limit = int(os.getenv("NEWS_MAX_STOCKS", "300"))
    sleep_sec = float(os.getenv("NEWS_SLEEP_SEC", "0.5"))

    with engine.connect() as conn:
        if args.codes:
            rows = conn.execute(
                text("SELECT code, company_name FROM listed_stocks WHERE code = ANY(:c)")
                if engine.dialect.name == "postgresql"
                else text("SELECT code, company_name FROM listed_stocks WHERE code IN :c").bindparams(
                    __import__("sqlalchemy").bindparam("c", expanding=True)),
                {"c": list(args.codes)},
            ).fetchall()
        else:
            rows = conn.execute(
                text("SELECT code, company_name FROM listed_stocks ORDER BY code LIMIT :n"), {"n": limit}
            ).fetchall()
    if not rows:
        print("対象の銘柄がありません（listed_stocks が空）。")
        return 0

    now = datetime.now(timezone.utc)
    total_saved = 0
    failed = 0
    for i, (code, name) in enumerate(rows, 1):
        try:
            items = collect_raw_articles(code, name or code)
            records = [r for r in (article_row(code, it, now) for it in items) if r]
            if not args.dry_run:
                total_saved += save_articles(engine, records)
            else:
                total_saved += len(records)
        except Exception as e:  # 1銘柄の失敗で全体を止めない
            failed += 1
            print(f"[news] {code} 失敗: {e}")
        if i % 50 == 0:
            print(f"[news] {i}/{len(rows)} 銘柄まで完了（記事 {total_saved} 件）")
        time.sleep(sleep_sec)

    print(f"[news] 完了: {len(rows)} 銘柄 / 記事 {total_saved} 件{'（保存せず）' if args.dry_run else ''} / 失敗 {failed}")
    return exit_code(len(rows), failed, total_saved, FETCH_STATS)


def exit_code(n_stocks: int, failed: int, total_articles: int, stats: dict) -> int:
    """
    取得が実質すべて失敗していたら 1 を返す（RSS の取得エラーは個別には握りつぶされるため、
    「記事 0 件・失敗 0」で成功扱いになってしまうのを防ぐ）。
    """
    if n_stocks and failed == n_stocks:
        return 1
    requests_total = stats.get("ok", 0) + stats.get("errors", 0)
    if total_articles == 0 and stats.get("errors", 0) > 0 and stats.get("ok", 0) == 0:
        print(f"[news] 取得が全て失敗しました（{requests_total} 件のリクエスト）。ネットワーク・取得元を確認してください。")
        return 1
    if requests_total and stats.get("errors", 0) / requests_total > 0.5:
        print(f"[news] 警告: 取得エラーが多い（{stats['errors']}/{requests_total}）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
