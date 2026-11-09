"""
銘柄 API
- GET /api/stocks/search      : 銘柄検索
- GET /api/stocks/{code}      : 銘柄情報
- GET /api/stocks/{code}/quotes: 日足データ（Pro: 全件、Free: 直近30日）
- GET /api/stocks/{code}/peers : 同業種内の順位・業種平均（全員）と、同業種の上位銘柄（Pro）
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.routers.signals import SECTOR_NAMES

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/search")
async def search_stocks(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(text("""
        SELECT code, company_name, market_code, sector_code
        FROM listed_stocks
        WHERE code ILIKE :q OR company_name ILIKE :q
        LIMIT 20
    """), {"q": f"%{q}%"})
    return {"stocks": [dict(r._mapping) for r in rows]}


@router.get("/{code}")
async def get_stock(code: str, db: AsyncSession = Depends(get_db)):
    row = await db.execute(text("""
        SELECT code, company_name, market_code, sector_code
        FROM listed_stocks WHERE code = :code
    """), {"code": code})
    stock = row.fetchone()
    if not stock:
        raise HTTPException(status_code=404, detail="銘柄が見つかりません")
    return dict(stock._mapping)


@router.get("/{code}/quotes")
async def get_quotes(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_pro = current_user.plan == "pro"
    date_filter = "" if is_pro else 'AND "Date" >= CURRENT_DATE - INTERVAL \'30 days\''

    rows = await db.execute(text(f"""
        SELECT "Date", "Open", "High", "Low", "Close", "Volume",
               "AdjustmentClose"
        FROM daily_quotes
        WHERE "Code" = :code {date_filter}
        ORDER BY "Date" DESC
        LIMIT 500
    """), {"code": code})
    return {"code": code, "quotes": [dict(r._mapping) for r in rows], "plan": current_user.plan}


PEERS_LIMIT = 5   # Pro に見せる同業種の上位銘柄数


@router.get("/{code}/peers")
async def get_peers(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    同じ業種の中での、この銘柄の「市場を上回る確率」の順位と業種平均。
    順位と平均は全員に、同業種の個別銘柄リストは Pro のみに返す（無料は閲覧件数を絞っているため）。
    """
    stock = (await db.execute(
        text("SELECT code, sector_code FROM listed_stocks WHERE code = :code"), {"code": code}
    )).fetchone()
    if not stock:
        raise HTTPException(status_code=404, detail="銘柄が見つかりません")

    sector_code = (stock.sector_code or "").strip()
    empty = {
        "code": code, "sector_code": sector_code or None,
        "sector_name": SECTOR_NAMES.get(sector_code, sector_code or None),
        "stock_count": 0, "rank": None, "avg_up_probability": None,
        "up_probability": None, "peers": [], "peers_locked": current_user.plan != "pro",
    }
    if not sector_code:
        return empty

    rows = await db.execute(text("""
        SELECT s.code, s.company_name, p.signal, p.up_probability
        FROM listed_stocks s
        JOIN predictions p ON p."Code" = s.code
        WHERE s.sector_code = :sector
          AND p.id IN (SELECT MAX(id) FROM predictions GROUP BY "Code")
    """), {"sector": sector_code})
    items = sorted(
        ({"code": r.code, "company_name": r.company_name or r.code, "signal": r.signal,
          "up_probability": float(r.up_probability)} for r in rows),
        key=lambda x: x["up_probability"], reverse=True,
    )
    if not items:
        return empty

    is_pro = current_user.plan == "pro"
    me = next((i for i, x in enumerate(items) if x["code"] == code), None)
    return {
        **empty,
        "stock_count": len(items),
        "rank": me + 1 if me is not None else None,
        "up_probability": items[me]["up_probability"] if me is not None else None,
        "avg_up_probability": round(sum(x["up_probability"] for x in items) / len(items), 4),
        "peers": [x for x in items if x["code"] != code][:PEERS_LIMIT] if is_pro else [],
    }
