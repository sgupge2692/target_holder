"""
J-Quants APIから日足データを取得してDBに保存するスクリプト
毎日15:35にCI/CDから実行される
"""
import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

JQUANTS_API_KEY = os.getenv("JQUANTS_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = "https://api.jquants.com/v2"

headers = {"x-api-key": JQUANTS_API_KEY}


def fetch_listed_stocks() -> pd.DataFrame:
    """上場銘柄一覧を取得"""
    resp = requests.get(f"{BASE_URL}/listed/info", headers=headers)
    resp.raise_for_status()
    return pd.DataFrame(resp.json().get("info", []))


def fetch_daily_quotes(code: str, from_date: str, to_date: str) -> pd.DataFrame:
    """指定銘柄の日足データを取得"""
    resp = requests.get(
        f"{BASE_URL}/prices/daily_quotes",
        headers=headers,
        params={"code": code, "from": from_date, "to": to_date},
    )
    resp.raise_for_status()
    return pd.DataFrame(resp.json().get("daily_quotes", []))


def save_to_db(df: pd.DataFrame, table_name: str):
    """DBに保存"""
    engine = create_engine(DATABASE_URL)
    df.to_sql(table_name, engine, if_exists="append", index=False)
    print(f"Saved {len(df)} rows to {table_name}")


def main():
    today = datetime.today()
    from_date = (today - timedelta(days=7)).strftime("%Y%m%d")
    to_date = today.strftime("%Y%m%d")

    print(f"Fetching data from {from_date} to {to_date}")

    # 銘柄一覧取得
    stocks = fetch_listed_stocks()
    print(f"Total listed stocks: {len(stocks)}")

    # 全銘柄の日足データ取得（レート制限に注意）
    all_quotes = []
    for _, stock in stocks.iterrows():
        code = stock["Code"]
        try:
            quotes = fetch_daily_quotes(code, from_date, to_date)
            if not quotes.empty:
                all_quotes.append(quotes)
        except Exception as e:
            print(f"Error fetching {code}: {e}")

    if all_quotes:
        df_all = pd.concat(all_quotes, ignore_index=True)
        save_to_db(df_all, "daily_quotes")
        print(f"Done. Total rows: {len(df_all)}")
    else:
        print("No data fetched.")


if __name__ == "__main__":
    main()
