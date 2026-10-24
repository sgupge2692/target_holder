"""
予測シグナル関連エンドポイント
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from datetime import date, timedelta
from typing import Optional
from pydantic import BaseModel

from ..database import get_db

router = APIRouter(prefix="/signals", tags=["signals"])


class SignalOut(BaseModel):
    code: str
    date: date
    signal: str
    up_probability: float
    company_name: Optional[str] = None

    class Config:
        from_attributes = True


class AccuracyOut(BaseModel):
    total: int
    correct: int
    accuracy: float
    up_count: int
    down_count: int
    up_accuracy: float
    down_accuracy: float


@router.get("/latest", response_model=list[SignalOut])
async def get_latest_signals(
    signal: Optional[str] = Query(None, description="UP / DOWN / 全て"),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """最新の予測シグナル一覧を返す"""
    sql = """
        SELECT p.code, p.date, p.signal, p.up_probability::float,
               s.company_name
        FROM predictions p
        LEFT JOIN listed_stocks s ON p.code = s.code
        WHERE p.date = (SELECT MAX(date) FROM predictions)
        {signal_filter}
        ORDER BY p.up_probability DESC
        LIMIT :limit
    """
    signal_filter = "AND p.signal = :signal" if signal else ""
    params = {"limit": limit}
    if signal:
        params["signal"] = signal.upper()

    result = await db.execute(text(sql.format(signal_filter=signal_filter)), params)
    rows = result.mappings().all()
    return [SignalOut(**r) for r in rows]


@router.get("/history/{code}", response_model=list[SignalOut])
async def get_signal_history(
    code: str,
    days: int = Query(30, le=365),
    db: AsyncSession = Depends(get_db),
):
    """銘柄ごとの予測履歴"""
    since = date.today() - timedelta(days=days)
    result = await db.execute(
        text("""
            SELECT p.code, p.date, p.signal, p.up_probability::float,
                   s.company_name
            FROM predictions p
            LEFT JOIN listed_stocks s ON p.code = s.code
            WHERE p.code = :code AND p.date >= :since
            ORDER BY p.date DESC
        """),
        {"code": code, "since": since},
    )
    rows = result.mappings().all()
    return [SignalOut(**r) for r in rows]


@router.get("/accuracy", response_model=AccuracyOut)
async def get_accuracy(
    days: int = Query(30, le=365, description="過去N日の精度"),
    db: AsyncSession = Depends(get_db),
):
    """予測精度の集計（actual_returnが記録済みのもの）"""
    since = date.today() - timedelta(days=days)
    result = await db.execute(
        text("""
            SELECT
                COUNT(*)                                          AS total,
                COUNT(*) FILTER (WHERE is_correct = true)        AS correct,
                COUNT(*) FILTER (WHERE signal = 'UP')            AS up_count,
                COUNT(*) FILTER (WHERE signal = 'DOWN')          AS down_count,
                COUNT(*) FILTER (WHERE signal = 'UP'  AND is_correct = true) AS up_correct,
                COUNT(*) FILTER (WHERE signal = 'DOWN' AND is_correct = true) AS down_correct
            FROM predictions
            WHERE date >= :since AND is_correct IS NOT NULL
        """),
        {"since": since},
    )
    row = result.mappings().one()
    total   = row["total"] or 0
    correct = row["correct"] or 0
    up_c    = row["up_count"] or 0
    down_c  = row["down_count"] or 0
    up_ok   = row["up_correct"] or 0
    down_ok = row["down_correct"] or 0

    return AccuracyOut(
        total=total,
        correct=correct,
        accuracy=round(correct / total, 4) if total else 0.0,
        up_count=up_c,
        down_count=down_c,
        up_accuracy=round(up_ok / up_c, 4) if up_c else 0.0,
        down_accuracy=round(down_ok / down_c, 4) if down_c else 0.0,
    )
