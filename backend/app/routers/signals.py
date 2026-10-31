"""
シグナル API
- GET /api/signals/latest         : 最新シグナル一覧（無料: 上位10件、Pro: 全件）
- GET /api/signals/history/{code} : 銘柄別シグナル履歴
- GET /api/signals/accuracy       : 精度サマリー（全期間）キャッシュ5分
- GET /api/signals/backtest/chart : 月別精度推移チャートデータ キャッシュ5分
"""
import csv
import io
from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.cache import cache_get, cache_set, cache_key

router = APIRouter(prefix="/api/signals", tags=["signals"])

FREE_SIGNAL_LIMIT = 10  # 無料プランで見られるシグナル数
CACHE_TTL_SHORT = 300   # 5分
CACHE_TTL_LONG = 1800   # 30分（バックテスト等）


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

    # 各銘柄の最新シグナルを1件取得（PostgreSQL / SQLite 両対応）
    rows = await db.execute(text(f"""
        SELECT p."Code", p."Date", p.signal, p.up_probability,
               p.actual_return, p.is_correct,
               p.explanation, p.key_factors,
               s.company_name
        FROM predictions p
        LEFT JOIN listed_stocks s ON s.code = p."Code"
        WHERE p.id IN (
            SELECT MAX(id) FROM predictions GROUP BY "Code"
        )
        {where}
        ORDER BY p.up_probability DESC
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


@router.get("/export/csv")
async def export_signals_csv(
    signal: Optional[str] = Query(None, regex="^(UP|DOWN)$"),
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """シグナル履歴を CSV でダウンロード（Pro 専用）"""
    if current_user.plan != "pro":
        raise HTTPException(status_code=403, detail="CSV エクスポートは Pro プラン限定です")

    where_parts = ['"Date" >= date(\'now\', \'-\' || :days || \' days\')']
    params: dict = {"days": days}
    if signal:
        where_parts.append("p.signal = :signal")
        params["signal"] = signal

    where_clause = "WHERE " + " AND ".join(where_parts)

    rows = await db.execute(text(f"""
        SELECT
            p."Code", s.company_name, p."Date", p.signal,
            ROUND(p.up_probability * 100, 2)  AS up_probability_pct,
            ROUND(p.actual_return  * 100, 4)  AS actual_return_pct,
            p.is_correct,
            p.explanation,
            p.predicted_at
        FROM predictions p
        LEFT JOIN listed_stocks s ON s.code = p."Code"
        {where_clause}
        ORDER BY p."Date" DESC, p."Code"
        LIMIT 10000
    """), params)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "コード", "銘柄名", "シグナル日", "シグナル",
        "上昇確率(%)", "実績リターン(%)", "的中",
        "AI説明", "予測日時",
    ])
    for r in rows:
        writer.writerow([
            r.Code, r.company_name, r.Date, r.signal,
            r.up_probability_pct, r.actual_return_pct,
            ("○" if r.is_correct else "×") if r.is_correct is not None else "",
            r.explanation or "",
            r.predicted_at,
        ])

    output.seek(0)
    filename = f"signals_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),  # BOM付き（Excel対応）
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/accuracy")
async def get_accuracy(db: AsyncSession = Depends(get_db)):
    """認証不要・精度サマリーは公開（Redis 5分キャッシュ）"""
    ck = cache_key("signals", "accuracy")
    cached = await cache_get(ck)
    if cached is not None:
        return cached

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
    result = {"accuracy": [dict(r._mapping) for r in rows]}
    await cache_set(ck, result, ttl=CACHE_TTL_SHORT)
    return result


@router.get("/backtest/chart")
async def get_backtest_chart(
    months: int = Query(default=12, ge=1, le=36),
    db: AsyncSession = Depends(get_db),
):
    """
    月別精度推移データ（認証不要・公開、Redis 30分キャッシュ）
    """
    ck = cache_key("signals", "backtest", str(months))
    cached = await cache_get(ck)
    if cached is not None:
        return cached

    # 月別精度（strftime は PostgreSQL / SQLite 両対応のサブセット）
    monthly_rows = await db.execute(text("""
        SELECT
            substr("Date", 1, 7)                                               AS month,
            signal,
            COUNT(*)                                                            AS total,
            SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)                        AS correct,
            ROUND(
                100.0 * SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0), 1
            )                                                                   AS accuracy_pct,
            ROUND(AVG(actual_return) * 100, 3)                                 AS avg_return_pct
        FROM predictions
        WHERE actual_return IS NOT NULL
          AND "Date" >= date('now', '-' || :months || ' months')
        GROUP BY substr("Date", 1, 7), signal
        ORDER BY month ASC, signal
    """), {"months": months})

    monthly_data: dict = {}
    for r in monthly_rows:
        m = r.month
        if m not in monthly_data:
            monthly_data[m] = {"month": m}
        monthly_data[m][f"{r.signal.lower()}_accuracy"] = float(r.accuracy_pct or 0)
        monthly_data[m][f"{r.signal.lower()}_total"]    = int(r.total)
        monthly_data[m][f"{r.signal.lower()}_avg_return"] = float(r.avg_return_pct or 0)

    # 累積リターン
    cumulative_rows = await db.execute(text("""
        SELECT
            "Date",
            ROUND(actual_return * 100, 3) AS daily_return_pct
        FROM predictions
        WHERE signal = 'UP'
          AND actual_return IS NOT NULL
          AND "Date" >= date('now', '-' || :months || ' months')
        ORDER BY "Date" ASC
    """), {"months": months})

    cumulative = []
    cum = 1.0
    for r in cumulative_rows:
        cum *= (1 + float(r.daily_return_pct or 0) / 100)
        cumulative.append({
            "date": str(r.Date),
            "cumulative_return_pct": round((cum - 1) * 100, 2),
        })

    # 全期間サマリー
    overall_rows = await db.execute(text("""
        SELECT
            signal,
            COUNT(*)                                                            AS total,
            SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)                        AS correct,
            ROUND(
                100.0 * SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0), 1
            )                                                                   AS accuracy_pct,
            ROUND(AVG(actual_return) * 100, 3)                                 AS avg_return_pct
        FROM predictions
        WHERE actual_return IS NOT NULL
        GROUP BY signal
        ORDER BY signal
    """))

    result = {
        "monthly": sorted(monthly_data.values(), key=lambda x: x["month"]),
        "cumulative_return": cumulative,
        "overall": [dict(r._mapping) for r in overall_rows],
    }
    await cache_set(ck, result, ttl=CACHE_TTL_LONG)
    return result
