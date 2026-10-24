"""
銘柄 API
- GET /api/stocks/search      : 銘柄検索
- GET /api/stocks/{code}      : 銘柄情報
- GET /api/stocks/{code}/quotes: 日足データ（Pro: 全件、Free: 直近30日）
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.auth import get_current_user
from app.database import get_db
from app.models import User

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
        from fastapi import HTTPException
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
