"""
資産管理 API
- GET    /api/assets/accounts              : 口座一覧
- POST   /api/assets/accounts              : 口座追加
- PATCH  /api/assets/accounts/{id}         : 口座更新
- DELETE /api/assets/accounts/{id}         : 口座削除

- GET    /api/assets/snapshots             : 残高一覧（期間指定可）
- POST   /api/assets/snapshots             : 残高記録（upsert）
- DELETE /api/assets/snapshots/{id}        : 残高削除

- GET    /api/assets/summary               : カテゴリ別合計 & 純資産
- GET    /api/assets/history               : 純資産推移（月次グラフ用）
"""
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, delete
from sqlalchemy.exc import IntegrityError

from app.auth import get_current_user
from app.database import get_db
from app.models import User, AssetAccount, AssetSnapshot

router = APIRouter(prefix="/api/assets", tags=["assets"])

# ─────────────────────────────────────────────
# Pydantic スキーマ
# ─────────────────────────────────────────────

VALID_CATEGORIES = {"cash", "stock", "realestate", "vehicle", "other", "liability"}


class AccountCreate(BaseModel):
    name: str
    category: str
    currency: str = "JPY"
    note: Optional[str] = None
    sort_order: int = 0


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    currency: Optional[str] = None
    note: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class SnapshotUpsert(BaseModel):
    account_id: int
    snapshot_date: date
    amount: float
    memo: Optional[str] = None


# ─────────────────────────────────────────────
# 口座 CRUD
# ─────────────────────────────────────────────

@router.get("/accounts")
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """口座・資産項目の一覧（最新残高付き）"""
    rows = await db.execute(text("""
        SELECT
            a.id,
            a.name,
            a.category,
            a.currency,
            a.note,
            a.is_active,
            a.sort_order,
            a.created_at,
            s.amount        AS latest_amount,
            s.snapshot_date AS latest_date
        FROM asset_accounts a
        LEFT JOIN LATERAL (
            SELECT amount, snapshot_date
            FROM asset_snapshots
            WHERE account_id = a.id
            ORDER BY snapshot_date DESC
            LIMIT 1
        ) s ON true
        WHERE a.user_id = :uid
        ORDER BY a.sort_order ASC, a.id ASC
    """), {"uid": current_user.id})
    return {"accounts": [dict(r._mapping) for r in rows]}


@router.post("/accounts", status_code=201)
async def create_account(
    body: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"カテゴリが不正です: {body.category}")

    acct = AssetAccount(
        user_id=current_user.id,
        name=body.name,
        category=body.category,
        currency=body.currency,
        note=body.note,
        sort_order=body.sort_order,
    )
    db.add(acct)
    await db.commit()
    await db.refresh(acct)
    return {"id": acct.id, "name": acct.name, "category": acct.category}


@router.patch("/accounts/{account_id}")
async def update_account(
    account_id: int,
    body: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = await db.execute(
        select(AssetAccount).where(
            AssetAccount.id == account_id,
            AssetAccount.user_id == current_user.id,
        )
    )
    acct = row.scalar_one_or_none()
    if not acct:
        raise HTTPException(status_code=404, detail="口座が見つかりません")

    if body.name is not None:
        acct.name = body.name
    if body.category is not None:
        if body.category not in VALID_CATEGORIES:
            raise HTTPException(status_code=422, detail="カテゴリが不正です")
        acct.category = body.category
    if body.currency is not None:
        acct.currency = body.currency
    if body.note is not None:
        acct.note = body.note
    if body.is_active is not None:
        acct.is_active = body.is_active
    if body.sort_order is not None:
        acct.sort_order = body.sort_order

    await db.commit()
    return {"id": acct.id, "updated": True}


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        delete(AssetAccount).where(
            AssetAccount.id == account_id,
            AssetAccount.user_id == current_user.id,
        )
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="口座が見つかりません")
    return {"deleted": True}


# ─────────────────────────────────────────────
# スナップショット CRUD
# ─────────────────────────────────────────────

@router.get("/snapshots")
async def list_snapshots(
    account_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """残高履歴一覧（口座ID・期間でフィルタ可）"""
    where_clauses = ["aa.user_id = :uid"]
    params: dict = {"uid": current_user.id}

    if account_id is not None:
        where_clauses.append("s.account_id = :account_id")
        params["account_id"] = account_id
    if from_date is not None:
        where_clauses.append("s.snapshot_date >= :from_date")
        params["from_date"] = from_date
    if to_date is not None:
        where_clauses.append("s.snapshot_date <= :to_date")
        params["to_date"] = to_date

    where_sql = " AND ".join(where_clauses)
    rows = await db.execute(text(f"""
        SELECT s.id, s.account_id, aa.name AS account_name, aa.category,
               s.snapshot_date, s.amount, s.memo, s.created_at
        FROM asset_snapshots s
        JOIN asset_accounts aa ON aa.id = s.account_id
        WHERE {where_sql}
        ORDER BY s.snapshot_date DESC, s.account_id ASC
        LIMIT 1000
    """), params)
    return {"snapshots": [dict(r._mapping) for r in rows]}


@router.post("/snapshots", status_code=201)
async def upsert_snapshot(
    body: SnapshotUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """残高を記録（同日付は上書き）"""
    # 口座がこのユーザーのものかチェック
    acct_row = await db.execute(
        select(AssetAccount).where(
            AssetAccount.id == body.account_id,
            AssetAccount.user_id == current_user.id,
        )
    )
    if not acct_row.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="口座が見つかりません")

    # 既存スナップショットを確認
    existing = await db.execute(
        select(AssetSnapshot).where(
            AssetSnapshot.account_id == body.account_id,
            AssetSnapshot.snapshot_date == body.snapshot_date,
        )
    )
    snap = existing.scalar_one_or_none()

    if snap:
        snap.amount = body.amount
        snap.memo = body.memo
    else:
        snap = AssetSnapshot(
            account_id=body.account_id,
            snapshot_date=body.snapshot_date,
            amount=body.amount,
            memo=body.memo,
        )
        db.add(snap)

    await db.commit()
    await db.refresh(snap)
    return {"id": snap.id, "upserted": True}


@router.delete("/snapshots/{snapshot_id}")
async def delete_snapshot(
    snapshot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ユーザー所有チェック付き削除
    row = await db.execute(text("""
        DELETE FROM asset_snapshots s
        USING asset_accounts aa
        WHERE s.id = :sid AND s.account_id = aa.id AND aa.user_id = :uid
        RETURNING s.id
    """), {"sid": snapshot_id, "uid": current_user.id})
    await db.commit()
    if not row.fetchone():
        raise HTTPException(status_code=404, detail="スナップショットが見つかりません")
    return {"deleted": True}


# ─────────────────────────────────────────────
# サマリー & 履歴
# ─────────────────────────────────────────────

@router.get("/summary")
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """カテゴリ別最新残高合計 & 純資産"""
    rows = await db.execute(text("""
        SELECT
            aa.category,
            SUM(latest.amount) AS total
        FROM asset_accounts aa
        JOIN LATERAL (
            SELECT amount
            FROM asset_snapshots
            WHERE account_id = aa.id
            ORDER BY snapshot_date DESC
            LIMIT 1
        ) latest ON true
        WHERE aa.user_id = :uid AND aa.is_active = true
        GROUP BY aa.category
    """), {"uid": current_user.id})

    by_category: dict[str, float] = {}
    for r in rows:
        by_category[r.category] = float(r.total)

    assets = sum(v for k, v in by_category.items() if k != "liability")
    liabilities = by_category.get("liability", 0.0)
    net_worth = assets - liabilities

    return {
        "by_category": by_category,
        "total_assets": assets,
        "total_liabilities": liabilities,
        "net_worth": net_worth,
    }


@router.get("/history")
async def get_history(
    months: int = 12,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """純資産の月次推移（最大 months ヶ月）"""
    rows = await db.execute(text("""
        WITH monthly AS (
            SELECT
                date_trunc('month', s.snapshot_date)::date AS month,
                aa.category,
                -- 各月の最終日のスナップショットを取る
                LAST_VALUE(s.amount) OVER (
                    PARTITION BY aa.id, date_trunc('month', s.snapshot_date)
                    ORDER BY s.snapshot_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ) AS amount
            FROM asset_snapshots s
            JOIN asset_accounts aa ON aa.id = s.account_id
            WHERE aa.user_id = :uid AND aa.is_active = true
              AND s.snapshot_date >= (CURRENT_DATE - (:months || ' months')::interval)::date
        ),
        monthly_dedup AS (
            SELECT DISTINCT month, category, amount FROM monthly
        )
        SELECT
            month,
            SUM(CASE WHEN category != 'liability' THEN amount ELSE 0 END) AS assets,
            SUM(CASE WHEN category  = 'liability' THEN amount ELSE 0 END) AS liabilities,
            SUM(CASE WHEN category != 'liability' THEN amount ELSE -amount END) AS net_worth
        FROM monthly_dedup
        GROUP BY month
        ORDER BY month ASC
    """), {"uid": current_user.id, "months": months})

    return {
        "history": [
            {
                "month": str(r.month),
                "assets": float(r.assets),
                "liabilities": float(r.liabilities),
                "net_worth": float(r.net_worth),
            }
            for r in rows
        ]
    }
