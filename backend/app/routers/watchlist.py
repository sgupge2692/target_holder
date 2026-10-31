"""
ウォッチリスト API
- GET    /api/watchlist            : 登録済み銘柄一覧（最新シグナル付き）
- POST   /api/watchlist/{code}     : 銘柄を登録
- DELETE /api/watchlist/{code}     : 銘柄を削除
- GET    /api/watchlist/{code}/status : 登録済みかどうかを返す
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, delete
from sqlalchemy.exc import IntegrityError

from app.auth import get_current_user
from app.database import get_db
from app.models import User, Watchlist

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

WATCHLIST_MAX = 30  # 無料プランの最大登録数
WATCHLIST_MAX_PRO = 300


@router.get("")
async def get_watchlist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ウォッチリスト一覧（最新シグナル・株価付き）"""
    # 相関サブクエリ方式（PostgreSQL / SQLite 両対応）
    rows = await db.execute(text("""
        SELECT
            w.code,
            w.company_name,
            w.created_at,
            (SELECT signal       FROM predictions WHERE "Code" = w.code ORDER BY predicted_at DESC LIMIT 1) AS signal,
            (SELECT up_probability FROM predictions WHERE "Code" = w.code ORDER BY predicted_at DESC LIMIT 1) AS up_probability,
            (SELECT is_correct   FROM predictions WHERE "Code" = w.code ORDER BY predicted_at DESC LIMIT 1) AS is_correct,
            (SELECT "Date"       FROM predictions WHERE "Code" = w.code ORDER BY predicted_at DESC LIMIT 1) AS signal_date,
            (SELECT "Close"      FROM daily_quotes WHERE "Code" = w.code ORDER BY "Date" DESC LIMIT 1) AS latest_price,
            (SELECT "AdjustmentClose" FROM daily_quotes WHERE "Code" = w.code ORDER BY "Date" DESC LIMIT 1) AS adj_close
        FROM watchlist w
        WHERE w.user_id = :uid
        ORDER BY w.created_at DESC
    """), {"uid": current_user.id})

    return {
        "watchlist": [dict(r._mapping) for r in rows],
        "plan": current_user.plan,
    }


@router.get("/{code}/status")
async def get_watchlist_status(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = await db.execute(
        select(Watchlist).where(
            Watchlist.user_id == current_user.id,
            Watchlist.code == code,
        )
    )
    return {"code": code, "watched": row.scalar_one_or_none() is not None}


@router.post("/{code}", status_code=201)
async def add_to_watchlist(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """銘柄をウォッチリストに追加"""
    max_items = WATCHLIST_MAX_PRO if current_user.plan == "pro" else WATCHLIST_MAX

    # 現在の登録数チェック
    count_row = await db.execute(text(
        "SELECT COUNT(*) FROM watchlist WHERE user_id = :uid"
    ), {"uid": current_user.id})
    count = count_row.scalar()
    if count >= max_items:
        raise HTTPException(
            status_code=400,
            detail=f"ウォッチリストは最大{max_items}件です。{'Proプランで最大300件になります。' if current_user.plan == 'free' else ''}",
        )

    # 銘柄名を取得
    stock_row = await db.execute(text(
        "SELECT company_name FROM listed_stocks WHERE code = :code"
    ), {"code": code})
    stock = stock_row.fetchone()
    company_name = stock.company_name if stock else None

    entry = Watchlist(
        user_id=current_user.id,
        code=code,
        company_name=company_name,
    )
    db.add(entry)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="既にウォッチリストに登録済みです")

    return {"code": code, "watched": True}


@router.delete("/{code}", status_code=200)
async def remove_from_watchlist(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        delete(Watchlist).where(
            Watchlist.user_id == current_user.id,
            Watchlist.code == code,
        )
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="ウォッチリストに登録されていません")
    return {"code": code, "watched": False}
