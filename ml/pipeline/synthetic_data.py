"""
合成データ（デモ・E2E テスト用）

市場共通の動き + 業種の動き + 銘柄固有の動き。直近の値動きが翌日にわずかに効く弱い構造を入れてある。
実在の銘柄・株価とは無関係。ここから出る精度に意味は無い（動作確認とデモ用）。

銘柄コードは実在の銘柄と見分けがつくように、名前の先頭に SYNTHETIC_NAME_PREFIX を付ける。
scripts/demo_data.py は、DB に合成データ以外が入っていたら実行を拒否する（本番・実データの保護）。
"""
import numpy as np
import pandas as pd

SECTORS = ["3650", "7050", "3250", "5250", "3700", "6100"]
SYNTHETIC_NAME_PREFIX = "合成銘柄"


def synthetic_code(k: int) -> str:
    return f"{1300 + k * 7}"


def synthetic_codes(n_stocks: int) -> list[str]:
    return [synthetic_code(k) for k in range(n_stocks)]


def synthetic_quotes(dates: pd.DatetimeIndex, n_stocks: int = 60, seed: int = 42) -> pd.DataFrame:
    """日足の合成データ（Code, Date, OHLCV, AdjustmentClose, sector, name）"""
    rng = np.random.default_rng(seed)
    market = rng.normal(0.0003, 0.008, len(dates))
    sector_move = {s: rng.normal(0, 0.005, len(dates)) for s in SECTORS}
    rows = []
    for k in range(n_stocks):
        code = synthetic_code(k)
        sector = SECTORS[k % len(SECTORS)]
        idio = rng.normal(0, 0.012, len(dates))
        ret = market + sector_move[sector] + idio
        ret[1:] += 0.05 * ret[:-1]              # 弱いモメンタム
        close = 1000 * (1 + k % 5) * np.cumprod(1 + ret)
        for i, d in enumerate(dates):
            c = float(close[i])
            hi, lo = c * (1 + abs(rng.normal(0, 0.006))), c * (1 - abs(rng.normal(0, 0.006)))
            rows.append({
                "Code": code, "Date": d.date(), "Open": round((hi + lo) / 2, 1), "High": round(hi, 1),
                "Low": round(lo, 1), "Close": round(c, 1), "Volume": int(rng.integers(100_000, 5_000_000)),
                "AdjustmentClose": round(c, 1), "sector": sector, "name": f"{SYNTHETIC_NAME_PREFIX}{k}",
            })
    return pd.DataFrame(rows)
