"""
実績リターンの自動記録スクリプト

daily_pipeline から呼ばれ、前日シグナルの actual_return / is_correct を
daily_quotes の終値データをもとに記録する。

Usage:
    python pipeline/backtest.py            # 前日分を記録（毎日 pipeline から呼ぶ）
    python pipeline/backtest.py --date 2024-01-15  # 特定日指定
    python pipeline/backtest.py --summary  # 精度サマリーを表示
"""
import os
import argparse
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


# ─────────────────────────────────────────────
# 実績リターン記録
# ─────────────────────────────────────────────

def record_actual_returns(target_date: date, engine) -> int:
    """
    target_date 時点のシグナルに対して、
    target_date の終値 → target_date+1 営業日の終値 の変化率を計算し
    actual_return / is_correct を更新する。

    Returns:
        更新した行数
    """
    with engine.begin() as conn:
        # target_date に予測されたシグナルで未記録のものを取得
        rows = conn.execute(text("""
            SELECT p.id, p."Code", p."Date", p.signal
            FROM predictions p
            WHERE p."Date" = :target_date
              AND p.actual_return IS NULL
        """), {"target_date": target_date}).fetchall()

    if not rows:
        print(f"[backtest] {target_date}: 未記録シグナルなし")
        return 0

    codes = list({r[1] for r in rows})
    # target_date と翌営業日の終値を取得（翌日は ±5 日以内で最初のデータ）
    with engine.connect() as conn:
        quotes = pd.read_sql(text("""
            SELECT "Code", "Date", "AdjustmentClose"
            FROM daily_quotes
            WHERE "Code" = ANY(:codes)
              AND "Date" BETWEEN :d_from AND :d_to
            ORDER BY "Code", "Date"
        """), conn, params={
            "codes": codes,
            "d_from": target_date,
            "d_to": target_date + timedelta(days=7),
        })

    updated = 0
    with engine.begin() as conn:
        for row_id, code, sig_date, signal in rows:
            code_q = quotes[quotes["Code"] == code].sort_values("Date")
            # sig_date の終値
            base = code_q[code_q["Date"] == pd.Timestamp(sig_date)]
            # sig_date より後の最初の営業日の終値（翌日）
            next_day = code_q[code_q["Date"] > pd.Timestamp(sig_date)]

            if base.empty or next_day.empty:
                continue  # データ未取得なのでスキップ

            close_base = float(base.iloc[0]["AdjustmentClose"])
            close_next = float(next_day.iloc[0]["AdjustmentClose"])

            if close_base == 0:
                continue

            actual_return = (close_next - close_base) / close_base

            if signal == "UP":
                is_correct = actual_return > 0
            elif signal == "DOWN":
                is_correct = actual_return < 0
            else:
                is_correct = None

            conn.execute(text("""
                UPDATE predictions
                SET actual_return = :actual_return,
                    is_correct    = :is_correct
                WHERE id = :id
            """), {
                "actual_return": actual_return,
                "is_correct": is_correct,
                "id": row_id,
            })
            updated += 1

    print(f"[backtest] {target_date}: {updated} 件更新")
    return updated


# ─────────────────────────────────────────────
# 精度サマリー
# ─────────────────────────────────────────────

def print_summary(engine):
    with engine.connect() as conn:
        df = pd.read_sql(text("""
            SELECT
                signal,
                COUNT(*)                              AS total,
                SUM(CASE WHEN is_correct THEN 1 END)  AS correct,
                ROUND(
                    100.0 * SUM(CASE WHEN is_correct THEN 1 END) / NULLIF(COUNT(*), 0),
                    2
                )                                     AS accuracy_pct,
                ROUND(AVG(actual_return) * 100, 4)    AS avg_return_pct
            FROM predictions
            WHERE actual_return IS NOT NULL
            GROUP BY signal
            ORDER BY signal
        """), conn)

    print("\n=== シグナル精度サマリー ===")
    print(df.to_string(index=False))

    # 月別精度
    monthly = pd.read_sql(text("""
        SELECT
            TO_CHAR("Date", 'YYYY-MM')                AS month,
            COUNT(*)                                  AS total,
            ROUND(
                100.0 * SUM(CASE WHEN is_correct THEN 1 END) / NULLIF(COUNT(*), 0),
                2
            )                                         AS accuracy_pct
        FROM predictions
        WHERE actual_return IS NOT NULL
        GROUP BY TO_CHAR("Date", 'YYYY-MM')
        ORDER BY month DESC
        LIMIT 12
    """), conn)

    print("\n=== 月別精度（直近12ヶ月）===")
    print(monthly.to_string(index=False))


# ─────────────────────────────────────────────
# エントリポイント
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=None,
                        help="記録対象日 YYYY-MM-DD（省略時は前営業日）")
    parser.add_argument("--summary", action="store_true",
                        help="精度サマリーを表示して終了")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)

    if args.summary:
        print_summary(engine)
        return

    if args.date:
        target = date.fromisoformat(args.date)
    else:
        # 前営業日（土日をスキップ）
        yesterday = date.today() - timedelta(days=1)
        while yesterday.weekday() >= 5:  # 5=土, 6=日
            yesterday -= timedelta(days=1)
        target = yesterday

    print(f"[backtest] 対象日: {target}")
    record_actual_returns(target, engine)


if __name__ == "__main__":
    main()
