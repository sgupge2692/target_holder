"""
J-Quants API v2 接続テストスクリプト

使い方:
  # .envにAPIキーを設定してから実行
  python ml/pipeline/test_api_connection.py

  # または直接APIキーを渡す
  JQUANTS_API_KEY=your_key python ml/pipeline/test_api_connection.py
"""
import os
import sys
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.jquants.com/v2"
API_KEY = os.getenv("JQUANTS_API_KEY")


def check(label: str, ok: bool, detail: str = ""):
    status = "✅" if ok else "❌"
    print(f"  {status} {label}", end="")
    if detail:
        print(f"  → {detail}", end="")
    print()
    return ok


def test_connection():
    print("=" * 50)
    print("J-Quants API v2 接続テスト")
    print("=" * 50)

    all_ok = True

    # 1. APIキー確認
    print("\n[1] APIキー確認")
    if API_KEY:
        masked = API_KEY[:4] + "****" + API_KEY[-4:] if len(API_KEY) > 8 else "****"
        all_ok &= check("APIキーが設定されている", True, f"({masked})")
    else:
        check("APIキーが設定されている", False, ".envにJQUANTS_API_KEYを設定してください")
        print("\n⚠️  APIキーなしではテストを続行できません")
        print("  取得先: https://jpx-jquants.com/")
        return False

    headers = {"x-api-key": API_KEY}

    # 2. 銘柄一覧エンドポイント
    print("\n[2] 銘柄一覧 (/v2/equities/master)")
    try:
        resp = requests.get(f"{BASE_URL}/equities/master", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            all_ok &= check("レスポンス 200 OK", True, f"{len(data)} 銘柄取得")
            if data:
                sample = data[0]
                all_ok &= check("レスポンス構造", "Code" in sample, f"フィールド: {list(sample.keys())[:5]}")
        elif resp.status_code == 401:
            all_ok &= check("認証", False, "APIキーが無効です。正しいキーか確認してください")
        elif resp.status_code == 403:
            all_ok &= check("認証", False, "プランでこのエンドポイントにアクセスできません")
        else:
            all_ok &= check(f"HTTPステータス {resp.status_code}", False, resp.text[:100])
    except requests.ConnectionError:
        all_ok &= check("ネットワーク接続", False, "api.jquants.comに接続できません")
    except requests.Timeout:
        all_ok &= check("タイムアウト", False, "10秒以内に応答がありません")

    # 3. 日足データエンドポイント（トヨタ自動車 7203 で確認）
    print("\n[3] 日足データ (/v2/equities/bars/daily) - トヨタ自動車(7203)")
    try:
        today = datetime.today()
        from_date = (today - timedelta(days=10)).strftime("%Y%m%d")
        to_date = today.strftime("%Y%m%d")

        resp = requests.get(
            f"{BASE_URL}/equities/bars/daily",
            headers=headers,
            params={"code": "7203", "from": from_date, "to": to_date},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            all_ok &= check("レスポンス 200 OK", True, f"{len(data)} 日分取得")
            if data:
                sample = data[0]
                required_cols = ["Date", "Code", "O", "H", "L", "C", "Vo"]
                has_cols = all(c in sample for c in required_cols)
                all_ok &= check(
                    "v2形式の列名 (O/H/L/C/Vo)",
                    has_cols,
                    f"実際のフィールド: {list(sample.keys())}"
                )
                if has_cols:
                    latest = data[-1]
                    print(f"\n     最新データ（{latest.get('Date')}）:")
                    print(f"       始値: {latest.get('O')}, 高値: {latest.get('H')}, 安値: {latest.get('L')}, 終値: {latest.get('C')}")
                    print(f"       出来高: {latest.get('Vo')}")
        elif resp.status_code == 401:
            all_ok &= check("認証", False, "APIキーが無効です")
        else:
            all_ok &= check(f"HTTPステータス {resp.status_code}", False, resp.text[:100])
    except Exception as e:
        all_ok &= check("エラー", False, str(e))

    # 4. ページネーション確認
    print("\n[4] ページネーション確認")
    try:
        resp = requests.get(f"{BASE_URL}/equities/master", headers=headers, timeout=10)
        if resp.status_code == 200:
            body = resp.json()
            has_pagination = "pagination_key" in body
            check(
                "pagination_keyフィールドの存在",
                True,  # あってもなくてもOK（1ページに収まる場合はない）
                f"{'あり' if has_pagination else 'なし（全データが1ページ内）'}"
            )
    except Exception:
        pass

    print("\n" + "=" * 50)
    if all_ok:
        print("✅ 全テスト合格！fetch_data.py を実行できます。")
        print("\n次のステップ:")
        print("  docker compose exec ml python pipeline/fetch_data.py")
    else:
        print("❌ テスト失敗。上記のエラーを確認してください。")
        print("\nAPIキーの取得:")
        print("  https://jpx-jquants.com/ でアカウント登録後、ダッシュボードからAPIキーを発行")
    print("=" * 50)

    return all_ok


if __name__ == "__main__":
    ok = test_connection()
    sys.exit(0 if ok else 1)
