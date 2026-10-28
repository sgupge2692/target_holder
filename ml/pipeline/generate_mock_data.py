"""
モックデータ生成スクリプト（J-Quants が使えない間の開発・テスト用）
主要20銘柄の日足データを乱数で生成してDBに保存する

v3 対応:
  - listed_stocks に sector_code を追加（セクター相対特徴量に必要）
  - feature_engineering.py が listed_stocks を JOIN して sector_code を取得
"""
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")

# (code, name, sector_code)
# sector_code は 33業種分類コードの簡略版
MOCK_STOCKS = [
    ("72030", "トヨタ自動車",           "3700"),   # 輸送用機器
    ("67580", "ソニーグループ",           "3650"),   # 電気機器
    ("99840", "ソフトバンクグループ",     "5250"),   # 情報・通信
    ("83060", "三菱UFJフィナンシャル",    "7050"),   # 銀行
    ("68610", "キーエンス",               "3650"),   # 電気機器
    ("40630", "信越化学工業",             "3150"),   # 化学
    ("80350", "東京エレクトロン",         "3650"),   # 電気機器
    ("69540", "ファナック",               "3650"),   # 電気機器
    ("79740", "任天堂",                   "3650"),   # 電気機器
    ("94320", "NTT",                     "5250"),   # 情報・通信
    ("94330", "KDDI",                    "5250"),   # 情報・通信
    ("45190", "中外製薬",                 "3250"),   # 医薬品
    ("60980", "リクルートホールディングス","6050"),   # サービス
    ("45430", "テルモ",                   "3450"),   # 精密機器
    ("77510", "キヤノン",                 "3650"),   # 電気機器
    ("63670", "ダイキン工業",             "3550"),   # 機械
    ("80580", "三菱商事",                 "6150"),   # 卸売
    ("51080", "ブリヂストン",             "3550"),   # ゴム製品 → 機械で代用
    ("43450", "シスメックス",             "3450"),   # 精密機器
    ("96830", "NTTドコモ",               "5250"),   # 情報・通信
]

def generate_listed_stocks(engine) -> None:
    """listed_stocks テーブルにモック銘柄情報（sector_code含む）を挿入"""
    rows = [
        {"code": code, "company_name": name, "sector_code": sector}
        for code, name, sector in MOCK_STOCKS
    ]
    df = pd.DataFrame(rows)
    df.to_sql("listed_stocks", engine, if_exists="replace", index=False)
    print(f"listed_stocks に {len(df)} 件保存（sector_code付き）")


def generate_quotes(code: str, name: str, days: int = 90) -> pd.DataFrame:
    """ランダムウォークで日足データ生成"""
    today = datetime.today()
    dates = pd.bdate_range(end=today, periods=days)  # 営業日のみ

    # 初期価格（銘柄ごとに異なる）
    seed = sum(ord(c) for c in code)
    rng = np.random.default_rng(seed)
    base_price = rng.integers(1000, 50000)

    # ランダムウォーク
    returns = rng.normal(0.0005, 0.015, len(dates))
    prices = base_price * np.cumprod(1 + returns)

    rows = []
    for i, date in enumerate(dates):
        close = prices[i]
        high = close * rng.uniform(1.0, 1.03)
        low = close * rng.uniform(0.97, 1.0)
        open_ = low + rng.uniform(0, 1) * (high - low)
        volume = int(rng.integers(100000, 5000000))
        rows.append({
            "Code": code,
            "Date": date.strftime("%Y-%m-%d"),
            "Open": round(open_, 1),
            "High": round(high, 1),
            "Low": round(low, 1),
            "Close": round(close, 1),
            "Volume": volume,
            "AdjustmentClose": round(close, 1),
            "CompanyName": name,
        })
    return pd.DataFrame(rows)


def main():
    engine = create_engine(DATABASE_URL)

    # listed_stocks（sector_code 含む）を先に保存
    generate_listed_stocks(engine)

    all_quotes = []
    for code, name, _sector in MOCK_STOCKS:
        df = generate_quotes(code, name, days=180)
        all_quotes.append(df)
        print(f"Generated {len(df)} rows for {code} {name}")

    df_all = pd.concat(all_quotes, ignore_index=True)
    df_all.to_sql("daily_quotes", engine, if_exists="replace", index=False)
    print(f"\n完了。合計 {len(df_all)} 件を daily_quotes に保存しました。")
    print("次のステップ: python pipeline/feature_engineering.py")


if __name__ == "__main__":
    main()
