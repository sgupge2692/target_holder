"""
管理画面API: /api/admin/*
管理者（is_admin=True）のみアクセス可能

エンドポイント:
  GET /api/admin/stats           — KPI サマリ
  GET /api/admin/users           — ユーザー一覧
  GET /api/admin/signals/daily   — 日次シグナル統計
  GET /api/admin/model/metrics   — モデル学習メトリクス履歴
  GET /api/admin/model/features  — 特徴量重要度（最新）
"""
import os
import json
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func

from app.auth import get_current_user
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_EMAILS = set(
    e.strip()
    for e in os.getenv("ADMIN_EMAILS", "").split(",")
    if e.strip()
)


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    """管理者権限チェック"""
    if current_user.email not in ADMIN_EMAILS and not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=403, detail="管理者権限が必要です")
    return current_user


# ── KPI サマリ ────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    today = date.today()
    month_start = today.replace(day=1)

    # ユーザー統計
    total_users_r = await db.execute(text("SELECT COUNT(*) FROM users WHERE is_active=true"))
    total_users = total_users_r.scalar() or 0

    pro_users_r = await db.execute(text("SELECT COUNT(*) FROM users WHERE plan='pro' AND is_active=true"))
    pro_users = pro_users_r.scalar() or 0

    new_users_month_r = await db.execute(
        text("SELECT COUNT(*) FROM users WHERE created_at >= :start"),
        {"start": month_start},
    )
    new_users_month = new_users_month_r.scalar() or 0

    # 推定月次MRR (¥2,980 × Proユーザー)
    mrr = pro_users * 2980

    # シグナル統計（過去30日）
    signal_stats_r = await db.execute(
        text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE signal='UP') as up_count,
                COUNT(*) FILTER (WHERE signal='DOWN') as down_count,
                COUNT(*) FILTER (WHERE actual_return IS NOT NULL) as evaluated,
                ROUND(
                  COUNT(*) FILTER (WHERE signal='UP' AND actual_return > 0)::numeric
                  / NULLIF(COUNT(*) FILTER (WHERE signal='UP' AND actual_return IS NOT NULL), 0)
                  * 100, 1
                ) as up_accuracy
            FROM predictions
            WHERE predicted_at >= NOW() - INTERVAL '30 days'
        """)
    )
    sig = signal_stats_r.fetchone()

    # 過去7日間の日次新規ユーザー
    daily_signups_r = await db.execute(
        text("""
            SELECT created_at::date as day, COUNT(*) as count
            FROM users
            WHERE created_at >= NOW() - INTERVAL '7 days'
            GROUP BY 1 ORDER BY 1
        """)
    )
    daily_signups = [{"date": str(r.day), "count": r.count} for r in daily_signups_r.fetchall()]

    return {
        "users": {
            "total": total_users,
            "pro": pro_users,
            "free": total_users - pro_users,
            "new_this_month": new_users_month,
            "conversion_rate_pct": round(pro_users / max(total_users, 1) * 100, 1),
        },
        "revenue": {
            "mrr": mrr,
            "arr": mrr * 12,
        },
        "signals": {
            "total_30d": sig.total or 0,
            "up_count_30d": sig.up_count or 0,
            "down_count_30d": sig.down_count or 0,
            "evaluated_30d": sig.evaluated or 0,
            "up_accuracy_30d": float(sig.up_accuracy) if sig.up_accuracy else None,
        },
        "daily_signups": daily_signups,
    }


# ── ユーザー一覧 ──────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    page: int = 1,
    per_page: int = 50,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    offset = (page - 1) * per_page
    total_r = await db.execute(text("SELECT COUNT(*) FROM users"))
    total = total_r.scalar() or 0

    result = await db.execute(
        text("""
            SELECT id, email, plan, is_active, email_signal_alert,
                   created_at, updated_at
            FROM users
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {"limit": per_page, "offset": offset},
    )
    rows = result.fetchall()
    users = [
        {
            "id": r.id,
            "email": r.email,
            "plan": r.plan,
            "is_active": r.is_active,
            "email_signal_alert": r.email_signal_alert,
            "created_at": str(r.created_at),
        }
        for r in rows
    ]
    return {"users": users, "total": total, "page": page, "per_page": per_page}


# ── 日次シグナル統計 ──────────────────────────────────────────────────────

@router.get("/signals/daily")
async def daily_signal_stats(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    result = await db.execute(
        text("""
            SELECT
                predicted_at::date as day,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE signal='UP') as up,
                COUNT(*) FILTER (WHERE signal='DOWN') as down,
                ROUND(
                  COUNT(*) FILTER (WHERE signal='UP' AND actual_return > 0)::numeric
                  / NULLIF(COUNT(*) FILTER (WHERE signal='UP' AND actual_return IS NOT NULL), 0)
                  * 100, 1
                ) as accuracy_pct
            FROM predictions
            WHERE predicted_at >= NOW() - (:days || ' days')::interval
            GROUP BY 1 ORDER BY 1 DESC
        """),
        {"days": days},
    )
    rows = result.fetchall()
    return {
        "data": [
            {
                "date": str(r.day),
                "total": r.total,
                "up": r.up,
                "down": r.down,
                "accuracy_pct": float(r.accuracy_pct) if r.accuracy_pct else None,
            }
            for r in rows
        ]
    }


# ── モデルメトリクス履歴 ──────────────────────────────────────────────────

@router.get("/model/metrics")
async def get_model_metrics(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """モデル学習メトリクス履歴（最新順）"""
    result = await db.execute(
        text("""
            SELECT id, trained_at, mode, mean_auc, std_auc,
                   lgbm_auc, xgb_auc, ensemble_auc, n_samples
            FROM model_metrics
            ORDER BY trained_at DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    rows = result.fetchall()
    return {
        "metrics": [
            {
                "id": r.id,
                "trained_at": str(r.trained_at),
                "mode": r.mode,
                "mean_auc": float(r.mean_auc) if r.mean_auc else None,
                "std_auc": float(r.std_auc) if r.std_auc else None,
                "lgbm_auc": float(r.lgbm_auc) if r.lgbm_auc else None,
                "xgb_auc": float(r.xgb_auc) if r.xgb_auc else None,
                "ensemble_auc": float(r.ensemble_auc) if r.ensemble_auc else None,
                "n_samples": r.n_samples,
            }
            for r in rows
        ]
    }


# ── 特徴量重要度 ──────────────────────────────────────────────────────────

@router.get("/model/features")
async def get_feature_importances(
    top_n: int = Query(default=20, ge=5, le=50),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """最新モデルの特徴量重要度（上位N件）"""
    result = await db.execute(
        text("""
            SELECT feature_importances, trained_at, mode
            FROM model_metrics
            WHERE feature_importances IS NOT NULL
            ORDER BY trained_at DESC
            LIMIT 1
        """)
    )
    row = result.fetchone()
    if not row:
        return {"features": [], "trained_at": None, "mode": None}

    fi_dict: dict = json.loads(row.feature_importances)
    sorted_fi = sorted(fi_dict.items(), key=lambda x: x[1], reverse=True)[:top_n]

    return {
        "features": [{"name": k, "importance": v} for k, v in sorted_fi],
        "trained_at": str(row.trained_at),
        "mode": row.mode,
    }
