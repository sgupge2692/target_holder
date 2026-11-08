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

def judge_signal(signal: str, excess_return: float):
    """
    シグナルの的中判定。モデルは「市場平均に対する相対的な強弱」を予測しているので、
    UP は市場を上回ったか、DOWN は市場を下回ったか（超過リターンの符号）で判定する。
    """
    if signal == "UP":
        return bool(excess_return > 0)
    if signal == "DOWN":
        return bool(excess_return < 0)
    return None


def calc_next_day_returns(quotes: pd.DataFrame, base_date: date) -> pd.Series:
    """
    銘柄ごとの「base_date の終値 → 翌営業日の終値」の騰落率を返す（index=Code）。
    base_date に終値がない銘柄、翌営業日のデータがない銘柄は含めない。
    """
    q = quotes.copy()
    q["Date"] = pd.to_datetime(q["Date"])
    base_ts = pd.Timestamp(base_date)

    base = q[q["Date"] == base_ts].set_index("Code")["AdjustmentClose"].astype(float)
    nxt = (
        q[q["Date"] > base_ts]
        .sort_values("Date")
        .groupby("Code")
        .first()["AdjustmentClose"]
        .astype(float)
    )
    both = pd.concat([base.rename("base"), nxt.rename("next")], axis=1).dropna()
    both = both[both["base"] != 0]
    return (both["next"] - both["base"]) / both["base"]


def record_actual_returns(target_date: date, engine) -> int:
    """
    target_date 時点のシグナルに対して、
    target_date の終値 → 翌営業日の終値 の変化率（actual_return）と、
    全銘柄の同期間の騰落率の中央値（market_return）を求め、
    excess_return = actual_return - market_return を記録して、超過リターンで的中判定する。

    Returns:
        更新した行数
    """
    with engine.begin() as conn:
        # target_date に予測されたシグナルで未記録のものを取得
        rows = conn.execute(text("""
            SELECT p.id, p."Code", p.signal
            FROM predictions p
            WHERE p."Date" = :target_date
              AND p.actual_return IS NULL
        """), {"target_date": target_date}).fetchall()

    if not rows:
        print(f"[backtest] {target_date}: 未記録シグナルなし")
        return 0

    # 市場平均の算出には「全銘柄」の終値が必要（predictions には UP/DOWN の銘柄しかない）
    with engine.connect() as conn:
        quotes = pd.read_sql(text("""
            SELECT "Code", "Date", "AdjustmentClose"
            FROM daily_quotes
            WHERE "Date" BETWEEN :d_from AND :d_to
        """), conn, params={
            "d_from": target_date,
            "d_to": target_date + timedelta(days=7),
        })

    returns = calc_next_day_returns(quotes, target_date)
    if returns.empty:
        print(f"[backtest] {target_date}: 翌営業日のデータ未取得のためスキップ")
        return 0
    market_return = float(returns.median())

    updated = 0
    with engine.begin() as conn:
        for row_id, code, signal in rows:
            if code not in returns.index:
                continue  # データ未取得なのでスキップ
            actual_return = float(returns.loc[code])
            excess_return = actual_return - market_return
            conn.execute(text("""
                UPDATE predictions
                SET actual_return = :actual_return,
                    market_return = :market_return,
                    excess_return = :excess_return,
                    is_correct    = :is_correct
                WHERE id = :id
            """), {
                "actual_return": actual_return,
                "market_return": market_return,
                "excess_return": excess_return,
                "is_correct": judge_signal(signal, excess_return),
                "id": row_id,
            })
            updated += 1

    print(f"[backtest] {target_date}: {updated} 件更新（市場中央値 {market_return:+.3%}）")
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
                ROUND(AVG(actual_return) * 100, 4)    AS avg_return_pct,
                ROUND(AVG(excess_return) * 100, 4)    AS avg_excess_pct
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
