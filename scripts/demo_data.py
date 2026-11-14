#!/usr/bin/env python3
"""
デモデータ生成 — 合成データで、本物のパイプラインを「毎日動かした」状態を作る

J-Quants・OpenAI・ニュース API なしで、画面（シグナル・バックテスト・業種別など）を確認できる。

  1. 合成の株価（ランダムウォーク）を入れる
  2. 特徴量 → リーク検査 → 学習 → 予測 を1回実行する
  3. 翌日以降の株価を1日ずつ追加し、毎日「実績記録 → 特徴量 → 予測」を繰り返す
     （学習は最初の1回だけ。以降の予測はすべて学習していない期間＝out-of-sample）

画面に出る的中率・累積超過リターンは、この合成データに対する本物の計算結果。
合成データには予測できる構造がほとんど無いので、**的中率は 50% 前後になる**（それが正しい）。
的中率を良く見せるための捏造は一切しない。

使い方（ML コンテナ、または ml の依存が入った環境から）:
  docker compose run --rm ml python /app/../scripts/demo_data.py --yes      # 例
  python scripts/demo_data.py --yes                                          # ローカル
  python scripts/demo_data.py --history 10 --stocks 30 --yes                 # 速く（動作確認用）

そのあと、デモユーザーと模擬売買を作る:
  docker compose run --rm backend python scripts/seed_demo.py

安全のための制限:
  - ENV=production のときは実行しない
  - DB に合成データ以外（実在の銘柄コード）が入っているときは実行を拒否する
    （特徴量テーブルなどを作り直すため、実データを消さないように）
"""
import argparse
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ML = ROOT / "ml"
PIPELINE = ML / "pipeline"
sys.path.insert(0, str(ML))

import pandas as pd
from sqlalchemy import create_engine, text

from pipeline.synthetic_data import synthetic_codes, synthetic_quotes

QUOTE_COLS = ["Code", "Date", "Open", "High", "Low", "Close", "Volume", "AdjustmentClose"]


def sync_url(url: str) -> str:
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


def foreign_codes(engine, synthetic: set[str]) -> dict[str, list[str]]:
    """合成データ以外のコードが入っているテーブルと、そのコード（最大5件）"""
    found: dict[str, list[str]] = {}
    with engine.connect() as conn:
        for table, col in (("daily_quotes", '"Code"'), ("predictions", '"Code"'), ("listed_stocks", "code")):
            try:
                rows = conn.execute(text(f"SELECT DISTINCT {col} FROM {table} LIMIT 5000")).fetchall()
            except Exception:
                conn.rollback()
                continue
            others = sorted({r[0] for r in rows} - synthetic)
            if others:
                found[table] = others[:5]
    return found


def run(script: str, args: list[str], env: dict, timeout: int = 1800) -> str:
    proc = subprocess.run(
        [sys.executable, str(PIPELINE / script), *args],
        cwd=str(ML), env=env, capture_output=True, text=True, timeout=timeout,
    )
    out = proc.stdout + proc.stderr
    if proc.returncode != 0:
        print(out[-3000:], file=sys.stderr)
        raise SystemExit(f"{script} が失敗しました (exit {proc.returncode})")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="合成データでデモ用の予測履歴を作る")
    ap.add_argument("--stocks", type=int, default=60, help="銘柄数（既定 60）")
    ap.add_argument("--days", type=int, default=420, help="最初に学習に使う営業日数（既定 420）")
    ap.add_argument("--history", type=int, default=30, help="日次運用をシミュレートする営業日数（既定 30）")
    ap.add_argument("--yes", action="store_true", help="確認なしで実行する")
    ap.add_argument("--model-dir", default=None, help="モデルの保存先（既定: 一時ディレクトリ。実運用のモデルを上書きしない）")
    args = ap.parse_args()

    if os.getenv("ENV", "").lower() == "production":
        print("ENV=production では実行しません（デモデータは開発用です）。", file=sys.stderr)
        return 2
    if "DATABASE_URL" not in os.environ:
        print("DATABASE_URL が設定されていません。", file=sys.stderr)
        return 2

    url = sync_url(os.environ["DATABASE_URL"])
    engine = create_engine(url)
    codes = synthetic_codes(args.stocks)

    others = foreign_codes(engine, set(codes))
    if others:
        print("実データが入っているため、実行を拒否します（特徴量などを作り直すため、実データが消えます）。", file=sys.stderr)
        for table, sample in others.items():
            print(f"  {table}: 合成データ以外のコードがあります（例: {', '.join(sample)}）", file=sys.stderr)
        print("デモ用の空の DB（docker compose の開発環境など）で実行してください。", file=sys.stderr)
        return 2

    host = engine.url.host
    print(f"対象 DB: {host}/{engine.url.database}")
    print(f"合成 {args.stocks} 銘柄 × {args.days} 営業日で学習し、その後 {args.history} 営業日を毎日運用する形で進めます。")
    print("既存の合成データ・特徴量・予測は作り直します。所要時間の目安: 数分〜10分。")
    if not args.yes:
        if input("続けますか？ [y/N] ").strip().lower() != "y":
            print("中止しました。")
            return 1

    # 1) 既存の合成データを消して、最初の営業日分を入れる
    all_dates = pd.bdate_range(end=pd.Timestamp(date.today()) - pd.offsets.BDay(1), periods=args.days + args.history)
    quotes = synthetic_quotes(all_dates, args.stocks)
    base_dates = [d.date() for d in all_dates[:args.days]]
    sim_dates = [d.date() for d in all_dates[args.days:]]

    with engine.begin() as conn:
        for table in ("predictions", "daily_quotes", "listed_stocks"):
            conn.execute(text(f"DELETE FROM {table}"))
        try:
            conn.execute(text("DROP TABLE IF EXISTS features"))
        except Exception:
            pass
        for r in quotes.drop_duplicates("Code")[["Code", "name", "sector"]].itertuples():
            conn.execute(text("INSERT INTO listed_stocks (code, company_name, sector_code) VALUES (:c,:n,:s)"),
                         {"c": r.Code, "n": r.name, "s": r.sector})
    quotes[quotes["Date"].isin(set(base_dates))][QUOTE_COLS].to_sql("daily_quotes", engine, if_exists="append", index=False)

    model_dir = args.model_dir or tempfile.mkdtemp(prefix="demo_models_")
    env = {**os.environ, "DATABASE_URL": url, "MODEL_DIR": model_dir, "OPENAI_API_KEY": "",
           "PYTHONPATH": str(ML), "MIN_SIGNALS_PER_SIDE": os.getenv("MIN_SIGNALS_PER_SIDE", "10")}

    # 2) 学習まで1回
    print("[1/3] 特徴量 → リーク検査 → 学習 → 予測")
    run("feature_engineering.py", [], env)
    run("sanity_checks.py", [], env)
    run("train.py", ["--mode", "ensemble"], env)
    run("predict.py", [], env)

    # 3) 1日ずつ進める（実績記録 → 特徴量 → 予測）。学習はしない（以降はすべて out-of-sample）
    print(f"[2/3] 日次運用のシミュレーション（{len(sim_dates)} 営業日）")
    prev = base_dates[-1]
    for i, d in enumerate(sim_dates, 1):
        quotes[quotes["Date"] == d][QUOTE_COLS].to_sql("daily_quotes", engine, if_exists="append", index=False)
        run("backtest.py", ["--date", prev.isoformat()], env)
        run("feature_engineering.py", [], env)
        run("predict.py", [], env)
        prev = d
        print(f"  {i}/{len(sim_dates)} {d}")

    # 4) 結果（DB に入った本物の計算結果）
    print("[3/3] 結果")
    with engine.connect() as conn:
        n_pred, n_dates = conn.execute(text('SELECT COUNT(*), COUNT(DISTINCT "Date") FROM predictions')).one()
        judged, hits = conn.execute(text(
            "SELECT COUNT(*), COALESCE(SUM(CASE WHEN is_correct THEN 1 ELSE 0 END),0) FROM predictions "
            "WHERE signal IN ('UP','DOWN') AND is_correct IS NOT NULL")).one()
    rate = f"{hits * 100.0 / judged:.1f}%" if judged else "-"
    print(f"  予測 {n_pred} 件 / {n_dates} 日分。判定済み {judged} 件、的中率(対市場) {rate}")
    print("  ※ 合成データなので的中率は 50% 前後になります（予測できる構造がほぼ無いため。これが正しい結果です）")
    print(f"  モデルの保存先: {model_dir}")
    print("\n次: docker compose run --rm backend python scripts/seed_demo.py  （デモユーザー・模擬売買）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
