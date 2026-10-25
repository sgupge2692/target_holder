"""
シグナル API
- GET /api/signals/latest   : 最新シグナル一覧（無料: 上位10件、Pro: 全件）
- GET /api/signals/history/{code}: 銘柄別シグナル履歴
- GET /api/signals/accuracy : 精度サマリー
"""
from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.auth import get_current_user
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/api/signals", tags=["signals"])

FREE_SIGNAL_LIMIT = 10  # 無料プランで見られるシグナル数


@router.get("/latest")
async def get_latest_signals(
    signal: Optional[str] = Query(None, regex="^(UP|DOWN)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_pro = current_user.plan == "pro"
    limit = 9999 if is_pro else FREE_SIGNAL_LIMIT

    where = 'WHERE p.signal = :signal' if signal else ""
    params: dict = {"limit": limit}
    if signal:
        params["signal"] = signal

    rows = await db.execute(text(f"""
        SELECT DISTINCT ON (p."Code")
               p."Code", p."Date", p.signal, p.up_probability,
               p.actual_return, p.is_correct,
               p.explanation, p.key_factors,
               s.company_name
        FROM predictions p
        LEFT JOIN listed_stocks s ON s.code = p."Code"
        {where}
        ORDER BY p."Code", p.predicted_at DESC
        LIMIT :limit
    """), params)

    result = [dict(r._mapping) for r in rows]
    return {"signals": result, "plan": current_user.plan, "total": len(result)}


@router.get("/history/{code}")
async def get_signal_history(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_pro = current_user.plan == "pro"
    limit = 9999 if is_pro else 5  # 無料は直近5件

    rows = await db.execute(text("""
        SELECT "Code", "Date", signal, up_probability, actual_return, is_correct,
               explanation, key_factors, predicted_at
        FROM predictions
        WHERE "Code" = :code
        ORDER BY "Date" DESC
        LIMIT :limit
    """), {"code": code, "limit": limit})

    return {"code": code, "history": [dict(r._mapping) for r in rows], "plan": current_user.plan}


@router.get("/accuracy")
async def get_accuracy(db: AsyncSession = Depends(get_db)):
    """認証不要・精度サマリーは公開"""
    rows = await db.execute(text("""
        SELECT
            signal,
            COUNT(*) AS total,
            SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS correct,
            ROUND(
                100.0 * SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0), 2
            ) AS accuracy_pct,
            ROUND(AVG(actual_return) * 100, 4) AS avg_return_pct
        FROM predictions
        WHERE actual_return IS NOT NULL
        GROUP BY signal
        ORDER BY signal
    """))
    return {"accuracy": [dict(r._mapping) for r in rows]}
