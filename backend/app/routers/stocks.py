"""
銘柄情報・価格データエンドポイント
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date, timedelta
from typing import Optional
from pydantic import BaseModel

from ..database import get_db

router = APIRouter(prefix="/stocks", tags=["stocks"])


class StockOut(BaseModel):
    code: str
    company_name: Optional[str]
    market_code: Optional[str]
    sector_code: Optional[str]


class QuoteOut(BaseModel):
    date: date
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[int]
    adj_close: Optional[float]


@router.get("/search", response_model=list[StockOut])
async def search_stocks(
    q: str = Query(..., min_length=1, description="銘柄コードまたは社名"),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """銘柄コード・社名で検索"""
    result = await db.execute(
        text("""
            SELECT code, company_name, market_code, sector_code
            FROM listed_stocks
            WHERE code ILIKE :q OR company_name ILIKE :q
            ORDER BY code
            LIMIT :limit
        """),
        {"q": f"%{q}%", "limit": limit},
    )
    rows = result.mappings().all()
    return [StockOut(**r) for r in rows]


@router.get("/{code}", response_model=StockOut)
async def get_stock(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT code, company_name, market_code, sector_code FROM listed_stocks WHERE code = :code"),
        {"code": code},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"銘柄 {code} が見つかりません")
    return StockOut(**row)


@router.get("/{code}/quotes", response_model=list[QuoteOut])
async def get_quotes(
    code: str,
    days: int = Query(60, le=730),
    db: AsyncSession = Depends(get_db),
):
    """日足データを返す（チャート描画用）"""
    since = date.today() - timedelta(days=days)
    result = await db.execute(
        text("""
            SELECT date,
                   open::float, high::float, low::float, close::float,
                   volume, adj_close::float
            FROM daily_quotes
            WHERE code = :code AND date >= :since
            ORDER BY date ASC
        """),
        {"code": code, "since": since},
    )
    rows = result.mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"銘柄 {code} の価格データがありません")
    return [QuoteOut(**r) for r in rows]
