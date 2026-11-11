"""
デモ用シードスクリプト（デモユーザーと模擬売買）

先に scripts/demo_data.py で、合成データの株価・予測履歴を作っておく（本物のパイプラインで計算する）。
このスクリプトは、それを画面で見るためのユーザーと、模擬売買のサンプルを作る。

  docker compose run --rm ml python /scripts/demo_data.py --yes        # 1. 合成データ + 予測履歴
  docker compose run --rm backend python scripts/seed_demo.py          # 2. このスクリプト
  docker compose run --rm backend python scripts/seed_demo.py --reset  # デモユーザーだけを消して作り直す

作るもの:
  - demo@kabumi.app      / demo1234 （Pro）
  - demo-free@kabumi.app / demo1234 （無料。シグナル閲覧が上位3件までになる様子を確認できる）
  - 模擬売買のサンプル: 合成データの実際の株価で、入口と出口を計算する（的中を作り込まない）

以前は、的中率が 6 割になるように乱数でシグナルと実績を捏造していた。画面の的中率が本物の成績と
誤解されるため廃止した。いまは、予測も実績も demo_data.py が本物のパイプラインで計算した結果を使う。

安全のための制限:
  - ENV=production では実行しない
  - 消すのはデモユーザー（とその模擬売買）だけ。予測・株価は消さない
"""
import argparse
import os
import sys
from datetime import date

import psycopg2
from passlib.context import CryptContext

DATABASE_URL = (
    os.environ.get("DATABASE_URL", "postgresql://stock:stock@db:5432/stockdb")
    .replace("postgresql+asyncpg://", "postgresql://")
    .replace("+asyncpg", "")
)

DEMO_USERS = [
    ("demo@kabumi.app", "pro"),
    ("demo-free@kabumi.app", "free"),
]
DEMO_PASSWORD = "demo1234"
PRO_EMAIL = DEMO_USERS[0][0]
DEMO_NOTE_PREFIX = "【デモ】"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 模擬売買: (何番目の銘柄, 入口が最新日の何営業日前か, 保有日数 / None=保有中)
PAPER_TRADES = [
    (0, 40, 5), (1, 36, 7), (2, 32, 5), (3, 28, 10), (4, 24, 3), (5, 20, 6),
    (6, 14, None), (7, 10, None), (8, 6, None), (9, 3, None),
]


def make_paper_trades(cur) -> list[tuple]:
    """合成データの実際の株価から、入口・出口の価格を取る（成績は作り込まない）"""
    cur.execute("SELECT code FROM listed_stocks ORDER BY code LIMIT 12")
    codes = [r[0] for r in cur.fetchall()]
    cur.execute('SELECT DISTINCT "Date" FROM daily_quotes ORDER BY "Date"')
    dates = [r[0] for r in cur.fetchall()]
    if not codes or len(dates) < 60:
        return []

    trades = []
    for idx, back, hold in PAPER_TRADES:
        if idx >= len(codes) or back >= len(dates):
            continue
        code = codes[idx]
        entry_i = len(dates) - 1 - back
        entry_date = dates[entry_i]
        cur.execute('SELECT "Close" FROM daily_quotes WHERE "Code" = %s AND "Date" = %s', (code, entry_date))
        row = cur.fetchone()
        if not row:
            continue
        entry_price = float(row[0])

        # そのときの予測（あれば）の向きにそろえる。無ければ UP
        cur.execute('SELECT signal FROM predictions WHERE "Code" = %s AND "Date" = %s ORDER BY id DESC LIMIT 1', (code, entry_date))
        s = cur.fetchone()
        signal = s[0] if s and s[0] in ("UP", "DOWN") else "UP"

        exit_date = exit_price = None
        status = "open"
        if hold is not None and entry_i + hold < len(dates):
            exit_date = dates[entry_i + hold]
            cur.execute('SELECT "Close" FROM daily_quotes WHERE "Code" = %s AND "Date" = %s', (code, exit_date))
            r2 = cur.fetchone()
            if r2:
                exit_price, status = float(r2[0]), "closed"
            else:
                exit_date = None
        trades.append((code, signal, entry_price, 100, entry_date, exit_price, exit_date, status,
                       f"{DEMO_NOTE_PREFIX}合成データの実際の値動きで計算"))
    return trades


def main():
    if os.environ.get("ENV", "").lower() == "production":
        print("ENV=production では実行しません（デモデータは開発用です）。", file=sys.stderr)
        sys.exit(2)

    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="デモユーザー（と模擬売買）を消して作り直す")
    args = parser.parse_args()

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        emails = [e for e, _ in DEMO_USERS]
        if args.reset:
            cur.execute("DELETE FROM paper_trades WHERE user_id IN (SELECT id FROM users WHERE email = ANY(%s))", (emails,))
            cur.execute("DELETE FROM users WHERE email = ANY(%s)", (emails,))
            conn.commit()
            print("デモユーザーを削除しました（予測・株価は残しています）。")

        cur.execute("SELECT COUNT(*) FROM predictions")
        if cur.fetchone()[0] == 0:
            print("予測データがありません。先に scripts/demo_data.py を実行してください。", file=sys.stderr)

        for email, plan in DEMO_USERS:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                print(f"{email} は作成済みです。")
                continue
            cur.execute(
                "INSERT INTO users (email, hashed_password, is_active, is_admin, plan, "
                "email_signal_alert, email_unsubscribed, created_at, updated_at) "
                "VALUES (%s,%s,true,false,%s,false,false,NOW(),NOW())",
                (email, pwd_context.hash(DEMO_PASSWORD), plan),
            )
            print(f"作成: {email} / {DEMO_PASSWORD}  (plan={plan})")
        conn.commit()

        cur.execute("SELECT id FROM users WHERE email = %s", (PRO_EMAIL,))
        uid = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM paper_trades WHERE user_id = %s", (uid,))
        if cur.fetchone()[0] > 0:
            print("模擬売買は作成済みです（作り直すには --reset）。")
        else:
            trades = make_paper_trades(cur)
            for code, signal, ep, shares, d_in, xp, d_out, status, note in trades:
                cur.execute(
                    """INSERT INTO paper_trades
                       (user_id, code, signal, entry_price, shares, entry_date, exit_price, exit_date, status, note)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (uid, code, signal, ep, shares, d_in, xp, d_out, status, note),
                )
            conn.commit()
            print(f"模擬売買 {len(trades)} 件を作成しました。" if trades else "株価データが足りないため、模擬売買は作成しませんでした。")

        print()
        print("=" * 56)
        print("  フロントエンド : http://localhost:3000")
        print(f"  Pro  : {DEMO_USERS[0][0]} / {DEMO_PASSWORD}")
        print(f"  無料 : {DEMO_USERS[1][0]} / {DEMO_PASSWORD}")
        print("  ※ 株価・予測は合成データ。的中率は 50% 前後になります")
        print("=" * 56)
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
