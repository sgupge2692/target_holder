"""
デモ用シードスクリプト
J-Quants・OpenAI なしでアプリの全機能を確認できるダミーデータを投入する。

使い方:
  docker compose run --rm backend python scripts/seed_demo.py
  docker compose run --rm backend python scripts/seed_demo.py --reset  # データを削除して再投入
"""
import argparse
import os
import random
import sys
import json
from datetime import date, datetime, timedelta, timezone

import psycopg2
from passlib.context import CryptContext

# ── 設定 ─────────────────────────────────────────────────────────────────────
DATABASE_URL = (
    os.environ.get("DATABASE_URL", "postgresql://stock:stock@db:5432/stockdb")
    .replace("postgresql+asyncpg://", "postgresql://")
    .replace("+asyncpg", "")
)

DEMO_EMAIL    = "demo@kabumi.app"
DEMO_PASSWORD = "demo1234"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── 日本株ダミーデータ ─────────────────────────────────────────────────────────
STOCKS = [
    ("7203", "トヨタ自動車",             "0050", "3700"),  # code, name, market, sector
    ("9984", "ソフトバンクグループ",       "0050", "5250"),
    ("6758", "ソニーグループ",             "0050", "3650"),
    ("8306", "三菱UFJフィナンシャル・G",   "0050", "7050"),
    ("9433", "KDDI",                      "0050", "5250"),
    ("6861", "キーエンス",                 "0050", "3650"),
    ("7974", "任天堂",                     "0050", "3650"),
    ("4063", "信越化学工業",               "0050", "3350"),
    ("8035", "東京エレクトロン",           "0050", "3650"),
    ("6098", "リクルートホールディングス", "0050", "7200"),
    ("2413", "エムスリー",                 "0050", "3650"),
    ("4519", "中外製薬",                   "0050", "3250"),
    ("6367", "ダイキン工業",               "0050", "3650"),
    ("9432", "日本電信電話",               "0050", "5250"),
    ("3382", "セブン&アイ・ホールディングス","0050","7200"),
    ("6981", "村田製作所",                 "0050", "3650"),
    ("4502", "武田薬品工業",               "0050", "3250"),
    ("7267", "本田技研工業",               "0050", "3700"),
    ("8316", "三井住友フィナンシャルG",    "0050", "7050"),
    ("6752", "パナソニックHD",             "0050", "3650"),
    ("2802", "味の素",                     "0050", "3050"),
    ("4661", "オリエンタルランド",         "0050", "7200"),
    ("8411", "みずほフィナンシャルG",      "0050", "7050"),
    ("9020", "東日本旅客鉄道",             "0050", "5050"),
    ("3659", "ネクソン",                   "0050", "3650"),
]

KEY_FACTORS_UP = [
    ["RSI 32.4 → 売られ過ぎ圏を脱出", "MA5がMA25をゴールデンクロス", "出来高が20日平均の2.1倍"],
    ["VWAP乖離+2.3%で買い優勢", "ボリンジャーバンド下限から反発", "MACDヒストグラムがプラス転換"],
    ["52週安値から+8.5%の水準", "機関投資家の買い越しを示す出来高急増", "RSI 41 → 中立から上昇転換"],
    ["前日比+1.2%で陽線確定", "ストキャスKDがシグナルラインを上抜け", "出来高モメンタム上昇"],
    ["MA75乖離-3.1%でサポート近辺", "下ヒゲ長く押し目買い優勢", "RoC(5日)+1.8%"],
]
KEY_FACTORS_DOWN = [
    ["RSI 72.3 → 買われ過ぎ圏に突入", "デッドクロス形成で下落トレンド示唆", "上ヒゲ長く戻り売り圧力"],
    ["52週高値から-2.1%で上値重い", "MACD乖離が拡大、調整示唆", "出来高急減でモメンタム低下"],
    ["ボリンジャーバンド上限に接触", "Williams %R -12 → 過熱域", "MA5乖離+4.2%で過熱感"],
    ["前日陰線で売り優勢続く", "ストキャスKD デッドクロス直後", "出来高比率0.6倍で閑散"],
    ["ATR比率上昇でボラ拡大リスク", "MACDヒストグラムがマイナス幅拡大", "RoC(20日)-3.2%で中期下落"],
]
EXPLANATIONS_UP = [
    "RSIが売られ過ぎ圏（30以下）を脱出し、ゴールデンクロスも形成。出来高急増が買い圧力の強さを示している。",
    "VWAP乖離がプラスに転じ買い優勢。ボリンジャー下限からの反発パターンでリバウンド期待が高い。",
    "52週安値付近のサポートラインで下げ止まり。機関投資家の買い越しを示唆する出来高パターンが見られる。",
    "短期・中期移動平均線が揃って上向き。ストキャスティクスがシグナルラインを上抜けし上昇モメンタムが確認できる。",
    "MA75乖離がマイナス圏でサポート付近。長い下ヒゲが押し目買い需要の強さを示している。",
]
EXPLANATIONS_DOWN = [
    "RSIが70超の買われ過ぎ圏に突入し、デッドクロスも形成。上ヒゲが長く戻り売り圧力が強い状況。",
    "52週高値付近で上値が重い。MACDの乖離拡大が調整局面入りを示唆、利益確定売りに注意。",
    "ボリンジャーバンド上限に接触し過熱感が高まる。Williams %Rが-12と過熱域に達している。",
    "前日の陰線に続き売り優勢が継続。出来高の急減でモメンタムが低下、じり安リスクがある。",
    "ATR比率の上昇でボラティリティ拡大局面。MACDヒストグラムのマイナス幅拡大で下落継続を示唆。",
]


def make_signal_rows(today: date, num_days: int = 60) -> list[dict]:
    rows = []
    rng = random.Random(42)

    for d in range(num_days):
        signal_date = today - timedelta(days=d + 1)
        if signal_date.weekday() >= 5:
            continue

        stocks_today = rng.sample(STOCKS, rng.randint(8, 15))
        for code, name, _market, _sector in stocks_today:
            is_up    = rng.random() < 0.60
            signal   = "UP" if is_up else "DOWN"
            up_prob  = rng.uniform(0.60, 0.85) if is_up else rng.uniform(0.15, 0.40)

            actual_return = None
            is_correct    = None
            if d >= 3:
                correct      = rng.random() < (0.62 if is_up else 0.58)
                is_correct   = correct
                if is_up and correct:
                    actual_return = rng.uniform(0.003, 0.025)
                elif is_up and not correct:
                    actual_return = rng.uniform(-0.018, -0.001)
                elif not is_up and correct:
                    actual_return = rng.uniform(-0.025, -0.003)
                else:
                    actual_return = rng.uniform(0.001, 0.015)

            explanation  = rng.choice(EXPLANATIONS_UP if is_up else EXPLANATIONS_DOWN)
            key_factors  = json.dumps(rng.choice(KEY_FACTORS_UP if is_up else KEY_FACTORS_DOWN), ensure_ascii=False)

            rows.append({
                "Code":         code,
                "Date":         signal_date.isoformat(),
                "up_probability": round(up_prob, 4),
                "signal":       signal,
                "predicted_at": datetime.combine(signal_date, datetime.min.time()).replace(tzinfo=timezone.utc),
                "explanation":  explanation,
                "key_factors":  key_factors,
                "actual_return": round(actual_return, 5) if actual_return is not None else None,
                "is_correct":   is_correct,
            })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="既存のデモデータを削除して再投入")
    args = parser.parse_args()

    print(f"Connecting to DB...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        if args.reset:
            print("Deleting existing data...")
            cur.execute("DELETE FROM predictions")
            cur.execute("SELECT id FROM users WHERE email = %s", (DEMO_EMAIL,))
            u = cur.fetchone()
            if u:
                cur.execute("DELETE FROM paper_trades WHERE user_id = %s", (u[0],))
            cur.execute("DELETE FROM listed_stocks WHERE code = ANY(%s)", ([c for c,*_ in STOCKS],))
            cur.execute("DELETE FROM users WHERE email = %s", (DEMO_EMAIL,))
            conn.commit()
            print("  Done.")

        # ── listed_stocks に銘柄名を登録 ─────────────────────────────────
        print("Upserting listed_stocks...")
        for code, name, market, sector in STOCKS:
            cur.execute(
                """
                INSERT INTO listed_stocks (code, company_name, market_code, sector_code)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE
                  SET company_name = EXCLUDED.company_name
                """,
                (code, name, market, sector),
            )
        conn.commit()
        print(f"  {len(STOCKS)} stocks registered.")

        # ── デモユーザー作成 ───────────────────────────────────────────────
        cur.execute("SELECT id FROM users WHERE email = %s", (DEMO_EMAIL,))
        if cur.fetchone():
            print(f"Demo user already exists, skipping.")
        else:
            hashed = pwd_context.hash(DEMO_PASSWORD)
            cur.execute(
                "INSERT INTO users (email, hashed_password, is_active, is_admin, plan) VALUES (%s,%s,true,false,'pro')",
                (DEMO_EMAIL, hashed),
            )
            conn.commit()
            print(f"Created demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}  (plan=pro)")

        # ── シグナルデータ投入 ─────────────────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM predictions")
        existing_count = cur.fetchone()[0]

        if existing_count > 0 and not args.reset:
            print(f"predictions table already has {existing_count} rows. Use --reset to overwrite.")
        else:
            today = date.today()
            rows  = make_signal_rows(today, num_days=60)
            print(f"Inserting {len(rows)} signal rows...")
            for r in rows:
                cur.execute(
                    """
                    INSERT INTO predictions
                      ("Code","Date",up_probability,signal,predicted_at,
                       explanation,key_factors,actual_return,is_correct)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                    """,
                    (r["Code"], r["Date"], r["up_probability"], r["signal"],
                     r["predicted_at"], r["explanation"], r["key_factors"],
                     r["actual_return"], r["is_correct"]),
                )
            conn.commit()
            print(f"  Done. ({len(rows)} rows)")

        # ── ペーパートレードデータ投入 ───────────────────────────────────────
        cur.execute("SELECT id FROM users WHERE email = %s", (DEMO_EMAIL,))
        demo_user = cur.fetchone()
        if demo_user:
            uid = demo_user[0]
            cur.execute("SELECT COUNT(*) FROM paper_trades WHERE user_id = %s", (uid,))
            pt_count = cur.fetchone()[0]

            if pt_count > 0 and not args.reset:
                print(f"paper_trades already has {pt_count} rows for demo user. Use --reset to overwrite.")
            else:
                if args.reset:
                    cur.execute("DELETE FROM paper_trades WHERE user_id = %s", (uid,))
                    conn.commit()

                today_d = date.today()
                rng_pt  = random.Random(99)
                PT_TRADES = [
                    # (code, signal, entry_price, shares, days_ago_entry, days_ago_exit_or_None, note)
                    ("7203",  "UP",   3680.0, 100,  45, 38, "トヨタ 長期トレンド順張り"),
                    ("6758",  "UP",   13200.0, 20, 40, 32, "ソニー 決算前の仕込み"),
                    ("9984",  "DOWN", 8900.0,  50, 35, 28, "ソフトバンク 空売り"),
                    ("8306",  "UP",   1180.0, 200, 30, 22, "三菱UFJ 金利上昇恩恵"),
                    ("6861",  "UP",   68000.0,  5, 25, 18, "キーエンス 押し目買い"),
                    ("7974",  "DOWN", 7200.0,  30, 20, 14, "任天堂 新作後の売り"),
                    ("4063",  "UP",   5800.0,  50, 60, 50, "信越化学 半導体需要"),
                    ("8035",  "UP",   22000.0, 10, 55, 45, "東京エレクトロン AI関連"),
                    # オープン中
                    ("9433",  "UP",   4850.0,  60, 10, None, "KDDI 高配当狙い"),
                    ("2802",  "UP",   3200.0,  80, 7,  None, "味の素 ディフェンシブ"),
                    ("4661",  "DOWN", 4100.0,  30, 5,  None, "オリランド 割高感"),
                    ("6981",  "UP",   2800.0, 100, 3,  None, "村田 EV関連期待"),
                ]

                print(f"Inserting paper trade demo rows...")
                for code, signal, entry_price, shares, d_entry, d_exit, note in PT_TRADES:
                    entry_date = today_d - timedelta(days=d_entry)
                    # 実際の株価に小さなランダム変動を加える
                    ep = round(entry_price * rng_pt.uniform(0.97, 1.03), 0)

                    if d_exit is not None:
                        exit_date = today_d - timedelta(days=d_exit)
                        # シグナル方向に合わせた終値（60〜70%的中）
                        correct = rng_pt.random() < 0.65
                        if signal == "UP":
                            xp = ep * (rng_pt.uniform(1.015, 1.045) if correct else rng_pt.uniform(0.975, 0.995))
                        else:
                            xp = ep * (rng_pt.uniform(0.960, 0.985) if correct else rng_pt.uniform(1.010, 1.030))
                        xp = round(xp, 0)
                        status = "closed"
                    else:
                        exit_date = None
                        xp = None
                        status = "open"

                    cur.execute(
                        """
                        INSERT INTO paper_trades
                          (user_id, code, signal, entry_price, shares, entry_date,
                           exit_price, exit_date, status, note)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (uid, code, signal, ep, shares, entry_date,
                         xp, exit_date, status, note),
                    )
                conn.commit()
                print(f"  Done. ({len(PT_TRADES)} paper trades)")

        print()
        print("=" * 52)
        print("  デモ起動完了！")
        print(f"  フロントエンド : http://localhost:3000")
        print(f"  Email          : {DEMO_EMAIL}")
        print(f"  Password       : {DEMO_PASSWORD}")
        print("=" * 52)

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
