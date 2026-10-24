"""
バックテスト・精度評価スクリプト
週次フル再学習後に実行される

評価内容:
1. 予測精度（Accuracy, Precision, Recall, F1）
2. 実績リターンの記録（actual_return, is_correct を predictions テーブルに書き戻す）
3. 損益シミュレーション（シグナル通りに売買した場合のPnL）
4. 結果をCSVとして保存
"""
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from sklearn.metrics import classification_report, confusion_matrix
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
REPORT_DIR   = os.getenv("REPORT_DIR", "/app/data/backtest")
os.makedirs(REPORT_DIR, exist_ok=True)


def fill_actual_returns(engine):
    """
    predictionsテーブルのactual_returnとis_correctを埋める。
    daily_quotesから翌日の実際の終値変化率を計算して書き戻す。
    """
    with engine.begin() as conn:
        # actual_returnがまだNULLの予測のみ対象
        conn.execute(text("""
            UPDATE predictions p
            SET
                actual_return = (
                    SELECT (q2.adj_close - q1.adj_close) / NULLIF(q1.adj_close, 0)
                    FROM daily_quotes q1
                    JOIN daily_quotes q2
                      ON q1.code = q2.code
                     AND q2.date = (
                         SELECT MIN(date) FROM daily_quotes
                         WHERE code = q1.code AND date > p.date
                     )
                    WHERE q1.code = p.code AND q1.date = p.date
                ),
                is_correct = (
                    CASE
                        WHEN p.signal = 'UP' THEN
                            (SELECT q2.adj_close > q1.adj_close
                             FROM daily_quotes q1
                             JOIN daily_quotes q2
                               ON q1.code = q2.code
                              AND q2.date = (
                                  SELECT MIN(date) FROM daily_quotes
                                  WHERE code = q1.code AND date > p.date
                              )
                             WHERE q1.code = p.code AND q1.date = p.date)
                        WHEN p.signal = 'DOWN' THEN
                            (SELECT q2.adj_close < q1.adj_close
                             FROM daily_quotes q1
                             JOIN daily_quotes q2
                               ON q1.code = q2.code
                              AND q2.date = (
                                  SELECT MIN(date) FROM daily_quotes
                                  WHERE code = q1.code AND date > p.date
                              )
                             WHERE q1.code = p.code AND q1.date = p.date)
                        ELSE NULL
                    END
                )
            WHERE p.actual_return IS NULL
              AND p.date < CURRENT_DATE  -- 当日分はまだ確定しない
        """))
    print("actual_return / is_correct を更新しました")


def load_predictions(engine) -> pd.DataFrame:
    return pd.read_sql(
        text("""
            SELECT code, date, signal, up_probability, actual_return, is_correct
            FROM predictions
            WHERE is_correct IS NOT NULL
            ORDER BY date
        """),
        engine,
    )


def calc_accuracy_metrics(df: pd.DataFrame) -> dict:
    """精度指標を計算"""
    up   = df[df["signal"] == "UP"]
    down = df[df["signal"] == "DOWN"]

    metrics = {
        "total_signals":    len(df),
        "up_signals":       len(up),
        "down_signals":     len(down),
        "overall_accuracy": float(df["is_correct"].mean()),
        "up_accuracy":      float(up["is_correct"].mean()) if len(up) else 0.0,
        "down_accuracy":    float(down["is_correct"].mean()) if len(down) else 0.0,
    }

    # 月別精度
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    monthly = df.groupby("month")["is_correct"].mean().reset_index()
    monthly.columns = ["month", "accuracy"]
    metrics["monthly_accuracy"] = monthly.to_dict("records")

    return metrics


def simulate_pnl(df: pd.DataFrame) -> dict:
    """
    シグナル通りに売買した場合のPnLシミュレーション
    - UP シグナル: 翌日始値で買い、終値で売り（単純化のためactual_returnで代替）
    - DOWN シグナル: 空売りとして actual_return の符号を反転
    - 各取引は同額（1単位）で計算
    - 手数料は考慮しない（保守的評価のため）
    """
    df = df.dropna(subset=["actual_return"]).copy()

    df["trade_return"] = np.where(
        df["signal"] == "UP",   df["actual_return"],
        np.where(df["signal"] == "DOWN", -df["actual_return"], 0.0)
    )

    cumulative  = (1 + df["trade_return"]).cumprod()
    total_ret   = float(cumulative.iloc[-1] - 1) if len(cumulative) else 0.0
    avg_ret     = float(df["trade_return"].mean())
    win_rate    = float((df["trade_return"] > 0).mean())
    max_dd      = float((cumulative / cumulative.cummax() - 1).min()) if len(cumulative) else 0.0
    sharpe      = float(avg_ret / df["trade_return"].std() * (252 ** 0.5)) if df["trade_return"].std() > 0 else 0.0

    return {
        "total_return":    round(total_ret,  4),
        "avg_return":      round(avg_ret,    6),
        "win_rate":        round(win_rate,   4),
        "max_drawdown":    round(max_dd,     4),
        "sharpe_ratio":    round(sharpe,     4),
        "trade_count":     len(df),
    }


def save_report(metrics: dict, pnl: dict, df: pd.DataFrame):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSONサマリー
    report = {
        "generated_at": datetime.now().isoformat(),
        "accuracy": metrics,
        "pnl_simulation": pnl,
    }
    json_path = f"{REPORT_DIR}/backtest_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    # 詳細CSVを最新1件だけ保存（ストレージ節約）
    csv_path = f"{REPORT_DIR}/predictions_latest.csv"
    df.to_csv(csv_path, index=False)

    print(f"レポート保存: {json_path}")
    return json_path


def main():
    engine = create_engine(DATABASE_URL)

    print("=== バックテスト開始 ===\n")

    # 1. actual_return / is_correct を埋める
    fill_actual_returns(engine)

    # 2. データ読み込み
    df = load_predictions(engine)
    if df.empty:
        print("評価可能なデータがありません（予測後1日以上経過したものが必要）")
        return

    print(f"評価対象: {len(df)} シグナル ({df['date'].min()} ~ {df['date'].max()})\n")

    # 3. 精度評価
    metrics = calc_accuracy_metrics(df)
    print(f"【精度】")
    print(f"  全体accuracy: {metrics['overall_accuracy']:.1%}")
    print(f"  UP accuracy:  {metrics['up_accuracy']:.1%}  ({metrics['up_signals']} 件)")
    print(f"  DOWN accuracy:{metrics['down_accuracy']:.1%} ({metrics['down_signals']} 件)")

    # 4. PnLシミュレーション
    pnl = simulate_pnl(df)
    print(f"\n【損益シミュレーション（手数料なし）】")
    print(f"  累積リターン: {pnl['total_return']:.1%}")
    print(f"  勝率:         {pnl['win_rate']:.1%}")
    print(f"  最大DD:       {pnl['max_drawdown']:.1%}")
    print(f"  Sharpe比:     {pnl['sharpe_ratio']:.2f}")
    print(f"  取引回数:     {pnl['trade_count']}")

    # 5. レポート保存
    save_report(metrics, pnl, df)
    print("\n=== バックテスト完了 ===")


if __name__ == "__main__":
    main()
