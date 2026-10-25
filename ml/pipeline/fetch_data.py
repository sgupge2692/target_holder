"""
J-Quants APIから日足データを取得してDBに保存するスクリプト
毎日15:35にCI/CDから実行される

使い方:
  python pipeline/fetch_data.py              # 全銘柄（直近7日）
  python pipeline/fetch_data.py --test       # 主要30銘柄のみ（動作確認用）
  python pipeline/fetch_data.py --days 90    # 直近90日
"""
import os
import sys
import argparse
import requests
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
BASE_URL = "https://api.jquants.com/v2"

# J-Quants 認証
JQUANTS_REFRESH_TOKEN = os.getenv("JQUANTS_REFRESH_TOKEN", "")
JQUANTS_MAIL_ADDRESS  = os.getenv("JQUANTS_MAIL_ADDRESS", "")
JQUANTS_PASSWORD      = os.getenv("JQUANTS_PASSWORD", "")

# テスト用主要銘柄（日経225の代表的な銘柄）
TEST_CODES = [
    "7203",  # トヨタ
    "6758",  # ソニー
    "9984",  # ソフトバンクG
    "8306",  # 三菱UFJ
    "6861",  # キーエンス
    "4063",  # 信越化学
    "8035",  # 東京エレクトロン
    "6954",  # ファナック
    "7974",  # 任天堂
    "4661",  # オリエンタルランド
    "9432",  # NTT
    "9433",  # KDDI
    "4519",  # 中外製薬
    "2413",  # エムスリー
    "6098",  # リクルート
    "4543",  # テルモ
    "7751",  # キヤノン
    "6367",  # ダイキン工業
    "8058",  # 三菱商事
    "5108",  # ブリヂストン
]


def get_id_token() -> str:
    """J-Quants IDトークン取得（リフレッシュトークンまたはメール/パスワードから）"""
    # リフレッシュトークンが直接設定されている場合
    if JQUANTS_REFRESH_TOKEN:
        resp = requests.post(
            f"{BASE_URL}/token/auth_refresh",
            params={"refreshtoken": JQUANTS_REFRESH_TOKEN},
        )
        resp.raise_for_status()
        return resp.json()["idToken"]

    # メール/パスワードから取得
    if JQUANTS_MAIL_ADDRESS and JQUANTS_PASSWORD:
        resp = requests.post(
            f"{BASE_URL}/token/auth_user",
            json={"mailaddress": JQUANTS_MAIL_ADDRESS, "password": JQUANTS_PASSWORD},
        )
        resp.raise_for_status()
        refresh_token = resp.json()["refreshToken"]
        resp2 = requests.post(
            f"{BASE_URL}/token/auth_refresh",
            params={"refreshtoken": refresh_token},
        )
        resp2.raise_for_status()
        return resp2.json()["idToken"]

    raise ValueError(
        "J-Quants 認証情報が設定されていません。\n"
        ".env に JQUANTS_REFRESH_TOKEN または JQUANTS_MAIL_ADDRESS + JQUANTS_PASSWORD を設定してください。"
    )


def fetch_listed_stocks(headers: dict) -> pd.DataFrame:
    """上場銘柄一覧を取得"""
    resp = requests.get(f"{BASE_URL}/listed/info", headers=headers)
    resp.raise_for_status()
    return pd.DataFrame(resp.json().get("info", []))


def fetch_daily_quotes(code: str, from_date: str, to_date: str, headers: dict) -> pd.DataFrame:
    """指定銘柄の日足データを取得"""
    resp = requests.get(
        f"{BASE_URL}/prices/daily_quotes",
        headers=headers,
        params={"code": code, "from": from_date, "to": to_date},
    )
    resp.raise_for_status()
    return pd.DataFrame(resp.json().get("daily_quotes", []))


def save_to_db(df: pd.DataFrame, table_name: str):
    """DBに保存（重複スキップ）"""
    engine = create_engine(DATABASE_URL)
    # 既存データと重複しないように upsert
    df.to_sql(table_name, engine, if_exists="append", index=False, method="multi")
    print(f"Saved {len(df)} rows to {table_name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="主要20銘柄のみ取得（動作確認用）")
    parser.add_argument("--days", type=int, default=7, help="直近何日分取得するか（デフォルト: 7）")
    args = parser.parse_args()

    today = datetime.today()
    from_date = (today - timedelta(days=args.days)).strftime("%Y%m%d")
    to_date = today.strftime("%Y%m%d")

    print(f"Fetching data from {from_date} to {to_date}")

    # 認証
    id_token = get_id_token()
    headers = {"Authorization": f"Bearer {id_token}"}
    print("認証成功")

    # 対象銘柄リスト
    if args.test:
        codes = TEST_CODES
        print(f"テストモード: {len(codes)} 銘柄")
    else:
        stocks = fetch_listed_stocks(headers)
        codes = stocks["Code"].tolist()
        print(f"全銘柄: {len(codes)} 銘柄")

    # 日足データ取得
    all_quotes = []
    for i, code in enumerate(codes):
        try:
            quotes = fetch_daily_quotes(code, from_date, to_date, headers)
            if not quotes.empty:
                all_quotes.append(quotes)
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(codes)} 完了")
        except Exception as e:
            print(f"Error fetching {code}: {e}")

    if all_quotes:
        df_all = pd.concat(all_quotes, ignore_index=True)
        save_to_db(df_all, "daily_quotes")
        print(f"完了。合計 {len(df_all)} 件")
    else:
        print("データが取得できませんでした。")


if __name__ == "__main__":
    main()
