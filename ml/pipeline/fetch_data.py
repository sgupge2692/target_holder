"""
J-Quants API v2 から日足データを取得してDBに保存するスクリプト
毎日15:35にCI/CDから実行される

v2仕様:
  - 認証: x-api-key ヘッダー（有効期限なし）
  - 銘柄一覧: GET /v2/equities/master
  - 日足データ: GET /v2/equities/bars/daily
  - レスポンス: {"data": [...], "pagination_key": "..."}
  - 列名: O/H/L/C/Vo/Va/AdjO/AdjH/AdjL/AdjC/AdjVo
"""
import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

JQUANTS_API_KEY = os.getenv("JQUANTS_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = "https://api.jquants.com/v2"

# プランごとのレート制限 (req/min): Free=5, Light=60, Standard=120, Premium=500
# デフォルトはFreeプランの上限に合わせて安全に設定
REQUESTS_PER_MINUTE = int(os.getenv("JQUANTS_RPM", "5"))
REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE  # 秒

headers = {"x-api-key": JQUANTS_API_KEY}


def _get_all_pages(url: str, params: dict) -> list:
    """ページネーションを処理して全データを返す"""
    all_data = []
    pagination_key = None

    while True:
        if pagination_key:
            params["pagination_key"] = pagination_key

        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        body = resp.json()

        data = body.get("data", [])
        all_data.extend(data)

        pagination_key = body.get("pagination_key")
        if not pagination_key:
            break

        time.sleep(REQUEST_INTERVAL)

    return all_data


def fetch_listed_stocks() -> pd.DataFrame:
    """上場銘柄一覧を取得 (v2: /v2/equities/master)"""
    data = _get_all_pages(f"{BASE_URL}/equities/master", {})
    df = pd.DataFrame(data)
    print(f"  上場銘柄数: {len(df)}")
    return df


def fetch_daily_quotes(code: str, from_date: str, to_date: str) -> pd.DataFrame:
    """指定銘柄の日足データを取得 (v2: /v2/equities/bars/daily)

    v2の列名:
      O=Open, H=High, L=Low, C=Close, Vo=Volume, Va=TurnoverValue
      AdjO/AdjH/AdjL/AdjC/AdjVo=調整済み, AdjFactor=調整係数
    """
    params = {"code": code, "from": from_date, "to": to_date}
    data = _get_all_pages(f"{BASE_URL}/equities/bars/daily", params)
    df = pd.DataFrame(data)

    if df.empty:
        return df

    # 列名をわかりやすく変換（DB保存用）
    rename_map = {
        "O": "open",
        "H": "high",
        "L": "low",
        "C": "close",
        "Vo": "volume",
        "Va": "turnover_value",
        "AdjO": "adj_open",
        "AdjH": "adj_high",
        "AdjL": "adj_low",
        "AdjC": "adj_close",
        "AdjVo": "adj_volume",
        "AdjFactor": "adj_factor",
        "Date": "date",
        "Code": "code",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    return df


def save_to_db(df: pd.DataFrame, table_name: str):
    """DBに保存（重複はスキップ）"""
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        # 一時テーブル経由でupsert
        df.to_sql(f"_tmp_{table_name}", conn, if_exists="replace", index=False)
        conn.execute(text(f"""
            INSERT INTO {table_name}
            SELECT * FROM _tmp_{table_name}
            ON CONFLICT (code, date) DO NOTHING
        """))
        conn.execute(text(f"DROP TABLE _tmp_{table_name}"))
    print(f"  {len(df)} 行を {table_name} に保存（重複スキップ）")


def main(full: bool = False):
    """
    Args:
        full: True の場合は過去2年分を取得（週次フル再学習用）
              False の場合は直近7日分のみ（日次差分更新）
    """
    today = datetime.today()
    if full:
        from_date = (today - timedelta(days=730)).strftime("%Y%m%d")
        print("=== フルデータ取得モード（過去2年分）===")
    else:
        from_date = (today - timedelta(days=7)).strftime("%Y%m%d")
        print("=== 差分取得モード（直近7日）===")

    to_date = today.strftime("%Y%m%d")
    print(f"期間: {from_date} → {to_date}")

    # 銘柄一覧取得
    print("\n[1/2] 上場銘柄一覧取得...")
    stocks = fetch_listed_stocks()

    # 日本株のみに絞る（ETFや外国株を除外）
    if "MarketCode" in stocks.columns:
        jp_stocks = stocks[stocks["MarketCode"].str.startswith(("1", "2", "3", "4"), na=False)]
    else:
        jp_stocks = stocks
    print(f"  対象銘柄数: {len(jp_stocks)}")

    # 全銘柄の日足データ取得
    print(f"\n[2/2] 日足データ取得（レート制限: {REQUESTS_PER_MINUTE} req/min）...")
    all_quotes = []
    errors = []

    for i, (_, stock) in enumerate(jp_stocks.iterrows()):
        code = stock.get("Code") or stock.get("code")
        if not code:
            continue

        try:
            quotes = fetch_daily_quotes(str(code), from_date, to_date)
            if not quotes.empty:
                all_quotes.append(quotes)

            # レート制限対応
            if i % 10 == 0:
                print(f"  {i}/{len(jp_stocks)} 件処理済み...")
            time.sleep(REQUEST_INTERVAL)

        except requests.HTTPError as e:
            errors.append({"code": code, "error": str(e)})
            if e.response.status_code == 429:
                print(f"  レート制限に達しました。60秒待機中...")
                time.sleep(60)
        except Exception as e:
            errors.append({"code": code, "error": str(e)})

    print(f"\n  取得完了: {len(all_quotes)} 銘柄, エラー: {len(errors)} 件")

    if errors:
        print(f"  エラー銘柄例: {errors[:3]}")

    if all_quotes:
        df_all = pd.concat(all_quotes, ignore_index=True)
        print(f"  合計 {len(df_all)} 行")

        if DATABASE_URL:
            save_to_db(df_all, "daily_quotes")
        else:
            # DB未設定時はCSVに保存（開発・テスト用）
            out_path = f"/app/data/daily_quotes_{to_date}.csv"
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            df_all.to_csv(out_path, index=False)
            print(f"  DB未設定のためCSVに保存: {out_path}")

        print(f"\n=== 完了 ===")
        return df_all
    else:
        print("データが取得できませんでした。APIキーを確認してください。")
        return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="過去2年分を全取得")
    args = parser.parse_args()
    main(full=args.full)
