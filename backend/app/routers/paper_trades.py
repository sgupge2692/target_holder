"""
ペーパートレード API
- GET  /api/paper-trades            : 自分のトレード一覧（open/closed/all）
- POST /api/paper-trades            : 新規トレード登録
- PATCH /api/paper-trades/{id}      : 決済（exit_price/exit_date）または編集
- DELETE /api/paper-trades/{id}     : 削除
- GET  /api/paper-trades/stats      : 損益サマリー
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.auth import get_current_user
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/api/paper-trades", tags=["paper_trades"])


# ── Pydantic スキーマ ──────────────────────────────────────────────────────────

class PaperTradeCreate(BaseModel):
    code: str = Field(..., max_length=10)
    signal: str = Field(..., pattern="^(UP|DOWN)$")
    entry_price: float = Field(..., gt=0)
    shares: int = Field(default=100, gt=0, le=100000)
    entry_date: date
    note: Optional[str] = None


class PaperTradeClose(BaseModel):
    exit_price: float = Field(..., gt=0)
    exit_date: date


class PaperTradeUpdate(BaseModel):
    exit_price: Optional[float] = None
    exit_date: Optional[date] = None
    shares: Optional[int] = None
    note: Optional[str] = None


# ── 損益計算ユーティリティ ─────────────────────────────────────────────────────

def _calc_pnl(signal: str, entry: float, exit_p: float, shares: int) -> float:
    """損益（円）を計算。UPはロング、DOWNはショート相当"""
    if signal == "UP":
        return (exit_p - entry) * shares
    else:
        return (entry - exit_p) * shares


def _calc_pnl_pct(signal: str, entry: float, exit_p: float) -> float:
    if signal == "UP":
        return (exit_p - entry) / entry * 100
    else:
        return (entry - exit_p) / entry * 100


# ── エンドポイント ─────────────────────────────────────────────────────────────

@router.get("")
async def list_paper_trades(
    status: Optional[str] = None,  # open / closed / all
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    where = "WHERE t.user_id = :uid"
    if status == "open":
        where += " AND t.status = 'open'"
    elif status == "closed":
        where += " AND t.status = 'closed'"

    rows = await db.execute(text(f"""
        SELECT t.id, t.code, t.signal, t.entry_price, t.shares,
               t.entry_date, t.exit_price, t.exit_date, t.status, t.note,
               t.created_at, s.company_name
        FROM paper_trades t
        LEFT JOIN listed_stocks s ON s.code = t.code
        {where}
        ORDER BY t.entry_date DESC, t.id DESC
        LIMIT 500
    """), {"uid": current_user.id})

    result = []
    for r in rows:
        row = dict(r._mapping)
        if row["exit_price"] and row["entry_price"]:
            row["pnl"] = round(_calc_pnl(row["signal"], float(row["entry_price"]), float(row["exit_price"]), row["shares"]), 0)
            row["pnl_pct"] = round(_calc_pnl_pct(row["signal"], float(row["entry_price"]), float(row["exit_price"])), 2)
        else:
            row["pnl"] = None
            row["pnl_pct"] = None
        result.append(row)
    return result


@router.post("", status_code=201)
async def create_paper_trade(
    body: PaperTradeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO paper_trades (user_id, code, signal, entry_price, shares, entry_date, status, note)
        VALUES (:uid, :code, :signal, :entry_price, :shares, :entry_date, 'open', :note)
        RETURNING id
    """), {
        "uid": current_user.id,
        "code": body.code.upper(),
        "signal": body.signal,
        "entry_price": body.entry_price,
        "shares": body.shares,
        "entry_date": body.entry_date,
        "note": body.note,
    })
    await db.commit()
    new_id = result.fetchone()[0]
    return {"id": new_id, "status": "created"}


@router.patch("/{trade_id}")
async def update_paper_trade(
    trade_id: int,
    body: PaperTradeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 所有確認
    row = await db.execute(
        text("SELECT id, signal, entry_price, shares FROM paper_trades WHERE id = :id AND user_id = :uid"),
        {"id": trade_id, "uid": current_user.id},
    )
    trade = row.fetchone()
    if not trade:
        raise HTTPException(status_code=404, detail="トレードが見つかりません")

    sets = []
    params: dict = {"id": trade_id}
    if body.exit_price is not None:
        sets.append("exit_price = :exit_price")
        params["exit_price"] = body.exit_price
    if body.exit_date is not None:
        sets.append("exit_date = :exit_date")
        params["exit_date"] = body.exit_date
    if body.shares is not None:
        sets.append("shares = :shares")
        params["shares"] = body.shares
    if body.note is not None:
        sets.append("note = :note")
        params["note"] = body.note

    # 決済情報が揃ったら closed に
    if body.exit_price and body.exit_date:
        sets.append("status = 'closed'")

    if not sets:
        return {"status": "no_change"}

    await db.execute(
        text(f"UPDATE paper_trades SET {', '.join(sets)}, updated_at = NOW() WHERE id = :id"),
        params,
    )
    await db.commit()
    return {"status": "updated"}


@router.delete("/{trade_id}", status_code=204)
async def delete_paper_trade(
    trade_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        text("DELETE FROM paper_trades WHERE id = :id AND user_id = :uid"),
        {"id": trade_id, "uid": current_user.id},
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="トレードが見つかりません")


@router.get("/stats")
async def get_paper_trade_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await db.execute(text("""
        SELECT signal, entry_price, exit_price, shares
        FROM paper_trades
        WHERE user_id = :uid AND status = 'closed'
          AND exit_price IS NOT NULL
    """), {"uid": current_user.id})
    trades = [dict(r._mapping) for r in rows]

    if not trades:
        return {"total": 0, "win": 0, "loss": 0, "win_rate": None, "total_pnl": 0, "avg_pnl_pct": None}

    pnls = [_calc_pnl(t["signal"], float(t["entry_price"]), float(t["exit_price"]), t["shares"]) for t in trades]
    pnl_pcts = [_calc_pnl_pct(t["signal"], float(t["entry_price"]), float(t["exit_price"])) for t in trades]
    wins = sum(1 for p in pnls if p > 0)

    return {
        "total": len(trades),
        "win": wins,
        "loss": len(trades) - wins,
        "win_rate": round(wins / len(trades) * 100, 1),
        "total_pnl": round(sum(pnls), 0),
        "avg_pnl_pct": round(sum(pnl_pcts) / len(pnl_pcts), 2),
        "best_pnl": round(max(pnls), 0),
        "worst_pnl": round(min(pnls), 0),
    }
