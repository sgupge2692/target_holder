"""
シグナル API
- GET /api/signals/latest         : 最新シグナル一覧（無料: 確度上位 FREE_SIGNAL_LIMIT 件、Pro: 全件）
- GET /api/signals/history/{code} : 銘柄別シグナル履歴
- GET /api/signals/accuracy       : 精度サマリー（全期間）キャッシュ5分
- GET /api/signals/backtest/chart : バックテスト（月別精度・累積超過リターン）公開・キャッシュ30分
- GET /api/signals/sectors        : 業種（東証33業種）別の強弱ヒートマップ。公開・キャッシュ5分
"""
import csv
import io
from typing import Optional
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.cache import cache_get, cache_set, cache_key

router = APIRouter(prefix="/api/signals", tags=["signals"])

FREE_SIGNAL_LIMIT = 3   # 無料プランで見られるシグナル数（課金動機の中核。変更はここだけ）
CACHE_TTL_SHORT = 300   # 5分
CACHE_TTL_LONG = 1800   # 30分（バックテスト等）

# 東証33業種コード → 業種名（listed_stocks.sector_code）
SECTOR_NAMES = {
    "0050": "水産・農林業", "1050": "鉱業", "2050": "建設業", "3050": "食料品",
    "3100": "繊維製品", "3150": "パルプ・紙", "3200": "化学", "3250": "医薬品",
    "3300": "石油・石炭製品", "3350": "ゴム製品", "3400": "ガラス・土石製品",
    "3450": "鉄鋼", "3500": "非鉄金属", "3550": "金属製品", "3600": "機械",
    "3650": "電気機器", "3700": "輸送用機器", "3750": "精密機器", "3800": "その他製品",
    "4050": "電気・ガス業", "5050": "陸運業", "5100": "海運業", "5150": "空運業",
    "5200": "倉庫・運輸関連業", "5250": "情報・通信業", "6050": "卸売業", "6100": "小売業",
    "7050": "銀行業", "7100": "証券・商品先物取引業", "7150": "保険業",
    "7200": "その他金融業", "8050": "不動産業", "9050": "サービス業",
}
MIN_STOCKS_PER_SECTOR = 3   # 銘柄数が少ない業種は平均がぶれるので除外


def _add_change(row: dict) -> dict:
    """
    前回の予測との差を付ける。
    - prob_change_pt : 上昇確率の変化（パーセントポイント）。前回が無ければ None
    - signal_changed : 前回からシグナルが変わったか（UP⇄DOWN など）。前回が無ければ None
    """
    prev_prob = row.get("prev_up_probability")
    prev_signal = row.get("prev_signal")
    row["prob_change_pt"] = (
        round((float(row["up_probability"]) - float(prev_prob)) * 100, 1)
        if prev_prob is not None else None
    )
    row["signal_changed"] = (prev_signal != row["signal"]) if prev_signal else None
    return row


@router.get("/latest")
async def get_latest_signals(
    signal: Optional[str] = Query(None, regex="^(UP|DOWN)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_pro = current_user.plan == "pro"
    limit = 9999 if is_pro else FREE_SIGNAL_LIMIT

    # 各銘柄の最新シグナルを1件取得（PostgreSQL / SQLite 両対応）
    # ※ フィルタは AND で連結する（WHERE の二重指定は構文エラーになる）
    signal_clause = "AND p.signal = :signal" if signal else ""
    params: dict = {}
    if signal:
        params["signal"] = signal

    # 無料ユーザーに「あと○件」を見せるため、制限前の総件数を別途数える
    count_row = await db.execute(text(f"""
        SELECT COUNT(*) AS n
        FROM predictions p
        WHERE p.id IN (
            SELECT MAX(id) FROM predictions GROUP BY "Code"
        )
        {signal_clause}
    """), params)
    total_available = int(count_row.scalar() or 0)

    # 確度の高い順（UP は上昇確率、DOWN は下落確率が高い順）。
    # 無料枠は「最も確度の高い数件」になるので、並び順が体験の質に直結する。
    rows = await db.execute(text(f"""
        SELECT p."Code", p."Date", p.signal, p.up_probability,
               p.actual_return, p.excess_return, p.is_correct,
               p.explanation, p.key_factors,
               s.company_name,
               (SELECT p2.up_probability FROM predictions p2
                 WHERE p2."Code" = p."Code" AND p2."Date" < p."Date"
                 ORDER BY p2."Date" DESC LIMIT 1) AS prev_up_probability,
               (SELECT p2.signal FROM predictions p2
                 WHERE p2."Code" = p."Code" AND p2."Date" < p."Date"
                 ORDER BY p2."Date" DESC LIMIT 1) AS prev_signal
        FROM predictions p
        LEFT JOIN listed_stocks s ON s.code = p."Code"
        WHERE p.id IN (
            SELECT MAX(id) FROM predictions GROUP BY "Code"
        )
        {signal_clause}
        ORDER BY CASE WHEN p.up_probability >= 0.5
                      THEN p.up_probability
                      ELSE 1 - p.up_probability END DESC
        LIMIT :limit
    """), {**params, "limit": limit})

    result = [_add_change(dict(r._mapping)) for r in rows]
    return {
        "signals": result,
        "plan": current_user.plan,
        "total": len(result),
        "total_available": total_available,
        "is_limited": (not is_pro) and total_available > len(result),
        "free_limit": FREE_SIGNAL_LIMIT,
    }


@router.get("/history/{code}")
async def get_signal_history(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_pro = current_user.plan == "pro"
    limit = 9999 if is_pro else 5  # 無料は直近5件

    rows = await db.execute(text("""
        SELECT "Code", "Date", signal, up_probability, actual_return, excess_return, is_correct,
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
    result = {"accuracy": [_jsonable(dict(r._mapping)) for r in rows]}
    await cache_set(ck, result, ttl=CACHE_TTL_SHORT)
    return result


# 累積リターンの「上位N件」。無料プランの閲覧上限・X 投稿と同じ件数で、実際に見られる銘柄の成績を出す
BACKTEST_TOP_K = FREE_SIGNAL_LIMIT


@router.get("/backtest/chart")
async def get_backtest_chart(
    months: int = Query(default=12, ge=1, le=36),
    db: AsyncSession = Depends(get_db),
):
    """
    バックテスト結果（認証不要・公開、Redis 30分キャッシュ）

    すべて「市場平均（全銘柄の騰落率の中央値）との比較」で集計する。
    - monthly           : 月別の的中率（is_correct は対市場の判定）
    - cumulative_return : UP シグナルの累積超過リターン
        * cumulative_return_pct     : 各日の UP シグナル全件の平均超過リターンを日次で積み上げ
        * top_cumulative_return_pct : 各日の確度上位 BACKTEST_TOP_K 件だけの同様の値
      シグナル 1 件ごとに複利をかけると、1 日に数百件あるため意味のない巨大な数字になる。
      必ず「日ごとに平均 → 日次で積み上げ」にする。
    - overall           : 全期間の的中率・平均リターン・平均超過リターン
    - meta              : 集計期間と営業日数（実績の長さを併記するため）
    """
    ck = cache_key("signals", "backtest", str(months))
    cached = await cache_get(ck)
    if cached is not None:
        return cached

    # 日付関数は DB 依存（SQLite の date('now', ...) は PostgreSQL に無い）ので Python 側で計算する
    cutoff = date.today() - timedelta(days=30 * months)

    # 月別精度。"Date" は PostgreSQL では DATE 型なので TEXT にキャストしてから切り出す
    monthly_rows = await db.execute(text("""
        SELECT
            substr(CAST("Date" AS TEXT), 1, 7)                                  AS month,
            signal,
            COUNT(*)                                                            AS total,
            SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)                        AS correct,
            ROUND(
                100.0 * SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0), 1
            )                                                                   AS accuracy_pct,
            ROUND(AVG(actual_return) * 100, 3)                                 AS avg_return_pct,
            ROUND(AVG(excess_return) * 100, 3)                                 AS avg_excess_pct
        FROM predictions
        WHERE actual_return IS NOT NULL
          AND "Date" >= :cutoff
        GROUP BY substr(CAST("Date" AS TEXT), 1, 7), signal
        ORDER BY month ASC, signal
    """), {"cutoff": cutoff})

    monthly_data: dict = {}
    for r in monthly_rows:
        m = r.month
        if m not in monthly_data:
            monthly_data[m] = {"month": m}
        key = r.signal.lower()
        monthly_data[m][f"{key}_accuracy"] = float(r.accuracy_pct or 0)
        monthly_data[m][f"{key}_total"] = int(r.total)
        monthly_data[m][f"{key}_avg_return"] = float(r.avg_return_pct or 0)
        monthly_data[m][f"{key}_avg_excess"] = float(r.avg_excess_pct or 0)

    # 累積超過リターン: 日ごとに平均してから積み上げる（全件 / 確度上位 K 件）
    daily_rows = await db.execute(text("""
        SELECT
            "Date",
            AVG(excess_return)                                  AS avg_all,
            AVG(CASE WHEN rk <= :k THEN excess_return END)      AS avg_top
        FROM (
            SELECT "Date", excess_return,
                   ROW_NUMBER() OVER (
                       PARTITION BY "Date" ORDER BY up_probability DESC
                   ) AS rk
            FROM predictions
            WHERE signal = 'UP'
              AND excess_return IS NOT NULL
              AND "Date" >= :cutoff
        ) t
        GROUP BY "Date"
        ORDER BY "Date" ASC
    """), {"cutoff": cutoff, "k": BACKTEST_TOP_K})

    cumulative = []
    cum_all, cum_top = 1.0, 1.0
    for r in daily_rows:
        cum_all *= 1 + float(r.avg_all or 0)
        cum_top *= 1 + float(r.avg_top or 0)
        cumulative.append({
            "date": str(r.Date)[:10],
            "cumulative_return_pct": round((cum_all - 1) * 100, 2),
            "top_cumulative_return_pct": round((cum_top - 1) * 100, 2),
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
            ROUND(AVG(actual_return) * 100, 3)                                 AS avg_return_pct,
            ROUND(AVG(excess_return) * 100, 3)                                 AS avg_excess_pct
        FROM predictions
        WHERE actual_return IS NOT NULL
        GROUP BY signal
        ORDER BY signal
    """))

    meta_row = (await db.execute(text("""
        SELECT MIN("Date") AS first_date, MAX("Date") AS last_date, COUNT(DISTINCT "Date") AS days
        FROM predictions
        WHERE actual_return IS NOT NULL
    """))).first()

    result = {
        "monthly": sorted(monthly_data.values(), key=lambda x: x["month"]),
        "cumulative_return": cumulative,
        "overall": [_jsonable(dict(r._mapping)) for r in overall_rows],
        "meta": {
            "first_date": str(meta_row.first_date)[:10] if meta_row and meta_row.first_date else None,
            "last_date": str(meta_row.last_date)[:10] if meta_row and meta_row.last_date else None,
            "days": int(meta_row.days) if meta_row and meta_row.days else 0,
            "top_k": BACKTEST_TOP_K,
        },
    }
    await cache_set(ck, result, ttl=CACHE_TTL_LONG)
    return result


def _jsonable(row: dict) -> dict:
    """PostgreSQL の NUMERIC は Decimal で返るので、JSON/キャッシュで扱える float / int にそろえる"""
    from decimal import Decimal
    return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in row.items()}


@router.get("/sectors")
async def get_sector_heatmap(db: AsyncSession = Depends(get_db)):
    """
    業種別の強弱（最新シグナルの集計）。公開エンドポイント。

    個別銘柄は返さず、業種ごとの「市場平均を上回る確率の平均」と UP / DOWN 件数だけを返す。
    どの業種が強いかを無料で見せ、個別銘柄は有料で見る導線にする。
    """
    key = cache_key("signals:sectors")
    cached = await cache_get(key)
    if cached is not None:
        return cached

    rows = await db.execute(text("""
        SELECT p."Date", p."Code", p.signal, p.up_probability, s.sector_code
        FROM predictions p
        LEFT JOIN listed_stocks s ON s.code = p."Code"
        WHERE p.id IN (SELECT MAX(id) FROM predictions GROUP BY "Code")
    """))
    records = [dict(r._mapping) for r in rows]

    groups: dict[str, list[dict]] = {}
    for r in records:
        code = (r.get("sector_code") or "").strip()
        if code:
            groups.setdefault(code, []).append(r)

    sectors = []
    for code, items in groups.items():
        if len(items) < MIN_STOCKS_PER_SECTOR:
            continue
        probs = [float(i["up_probability"]) for i in items]
        sectors.append({
            "sector_code": code,
            "sector_name": SECTOR_NAMES.get(code, code),
            "stock_count": len(items),
            "avg_up_probability": round(sum(probs) / len(probs), 4),
            "up_count": sum(1 for i in items if i["signal"] == "UP"),
            "down_count": sum(1 for i in items if i["signal"] == "DOWN"),
        })
    sectors.sort(key=lambda x: x["avg_up_probability"], reverse=True)

    dates = [str(r["Date"])[:10] for r in records if r.get("Date") is not None]
    result = _jsonable({
        "date": max(dates) if dates else None,
        "sectors": sectors,
        "min_stocks": MIN_STOCKS_PER_SECTOR,
    })
    await cache_set(key, result, CACHE_TTL_SHORT)
    return result

