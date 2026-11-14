"""
予想バトル API（AI vs あなた）
- GET  /api/battle/today        : 今日の出題（毎日全員共通の BATTLE_ROUND_SIZE 銘柄）と自分の回答状況
- POST /api/battle/pick         : 予想を送信（「市場平均より上 / 下」。送信後は変更不可）
- GET  /api/battle/me           : 自分の戦績（勝敗・連勝・称号・直近の対戦）
- GET  /api/battle/leaderboard  : ランキング（匿名ハンドル。公開・キャッシュ5分）

設計メモ
- 出題日 = predictions の最新の "Date"。出題銘柄は日付と銘柄コードのハッシュで決める（全員共通・再現可能）。
- AI の予想は結果が出るまで伏せる（答え合わせの演出になり、無料プランの表示制限も迂回されない）。
- 結果は保存せず predictions の excess_return から都度計算する（実績記録バッチと二重管理にならない）。
  的中判定は ml/pipeline/backtest.judge_signal と同じ: UP は excess>0、DOWN は excess<0（0 はどちらも外れ）。
- これはゲームであり投資助言ではない。
"""
import hashlib
import math
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.cache import cache_get, cache_set, cache_key
from app.database import get_db
from app.models import BattlePick, User

router = APIRouter(prefix="/api/battle", tags=["battle"])

BATTLE_ROUND_SIZE = 5          # 1日に出題する銘柄数
LEADERBOARD_MIN_PICKS = 10     # ランキングに載る最低の確定済み対戦数
LEADERBOARD_SIZE = 20
TITLE_MIN_PICKS = 20           # 称号（的中率ベース）を付ける最低の確定済み対戦数。少数では運の影響が大きい
CACHE_TTL = 300

DISCLAIMER = "これは予想を楽しむゲームです。投資の助言・勧誘ではありません。"


# ── 純粋関数（DB なしでテストできる） ────────────────────────────────────────

def is_pick_correct(pick: str, excess_return: Optional[float]) -> Optional[bool]:
    """超過リターンが未確定なら None。0 はどちらの向きでも外れ（backtest.judge_signal と同じ）"""
    if excess_return is None:
        return None
    return excess_return > 0 if pick == "UP" else excess_return < 0


def duel_outcome(user_ok: Optional[bool], ai_ok: Optional[bool]) -> Optional[str]:
    """win: あなただけ正解 / lose: AI だけ正解 / draw: 両方正解 or 両方不正解"""
    if user_ok is None or ai_ok is None:
        return None
    if user_ok and not ai_ok:
        return "win"
    if ai_ok and not user_ok:
        return "lose"
    return "draw"


def choose_round(candidates: list[dict], round_date: str, size: int = BATTLE_ROUND_SIZE) -> list[dict]:
    """日付と銘柄コードのハッシュ順で size 件を選ぶ。全員共通で、同じ入力なら同じ結果"""
    def key(c: dict) -> str:
        return hashlib.sha1(f"{round_date}:{c['Code']}".encode()).hexdigest()
    return sorted(candidates, key=key)[:size]


def streaks(results: list[bool]) -> tuple[int, int]:
    """古い順の勝敗列から (現在の連勝, 最大連勝)"""
    best = cur = 0
    for ok in results:
        cur = cur + 1 if ok else 0
        best = max(best, cur)
    return cur, best


def wilson_lower(wins: int, n: int, z: float = 1.96) -> float:
    """的中率の信頼区間の下限。少ない試行数での「たまたまの高勝率」が上位に来ないようにする"""
    if n == 0:
        return 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return (centre - margin) / denom


def handle_for(user_id: int) -> str:
    """ランキング用の匿名ハンドル（メールアドレスは出さない）"""
    return "投資家#" + hashlib.sha1(f"kabumi-battle:{user_id}".encode()).hexdigest()[:4].upper()


def title_for(settled: int, win_rate: float, best_streak: int) -> str:
    if settled < TITLE_MIN_PICKS:
        return "見習いトレーダー" if best_streak < 3 else "ビギナーズラック?"
    if win_rate >= 0.60:
        return "株の仙人"
    if win_rate >= 0.55:
        return "相場の読み手"
    if win_rate >= 0.45:
        return "ふつうの投資家"
    return "逆張りの達人"  # 一貫して外すなら、逆に張ればよい、という冗談


# ── スキーマ ─────────────────────────────────────────────────────────────────

class PickIn(BaseModel):
    code: str = Field(..., max_length=10)
    pick: str = Field(..., pattern="^(UP|DOWN)$")


# ── 内部クエリ ────────────────────────────────────────────────────────────────

async def _round_date(db: AsyncSession) -> Optional[str]:
    row = await db.execute(text("""SELECT MAX("Date") FROM predictions WHERE signal IN ('UP','DOWN')"""))
    d = row.scalar()
    return str(d)[:10] if d else None


async def _today_round(db: AsyncSession, round_date: str) -> list[dict]:
    """出題日の候補から BATTLE_ROUND_SIZE 件。同じ (Code, Date) に複数行あれば id が最大のものだけ"""
    rows = await db.execute(text("""
        SELECT p.id AS prediction_id, p."Code", p."Date", p.excess_return, s.company_name, s.sector_code
        FROM predictions p
        LEFT JOIN listed_stocks s ON s.code = p."Code"
        WHERE p.id IN (SELECT MAX(id) FROM predictions WHERE "Date" = :d GROUP BY "Code")
          AND p.signal IN ('UP','DOWN')
    """), {"d": date.fromisoformat(round_date)})   # PostgreSQL の DATE 列には文字列でなく date を渡す
    cands = [dict(r._mapping) for r in rows]
    return choose_round(cands, round_date)


async def _prices(db: AsyncSession, code: str) -> dict:
    """出題時の判断材料: 直近の終値と5営業日前比。価格が無い銘柄は None"""
    rows = await db.execute(text("""
        SELECT COALESCE("AdjustmentClose", "Close") AS c FROM daily_quotes
        WHERE "Code" = :c ORDER BY "Date" DESC LIMIT 6
    """), {"c": code})
    closes = [float(r[0]) for r in rows if r[0] is not None]
    if not closes:
        return {"close": None, "change_5d_pct": None}
    change = (closes[0] / closes[-1] - 1) * 100 if len(closes) >= 6 and closes[-1] else None
    return {"close": closes[0], "change_5d_pct": round(change, 2) if change is not None else None}


async def _my_duels(db: AsyncSession, user_id: int) -> list[dict]:
    """自分の全対戦（古い順）。AI の予想と結果を結合し、結果が出るまで AI の予想は伏せる"""
    rows = await db.execute(text("""
        SELECT b.id AS pick_id, b.code, b.round_date, b.pick,
               p.signal AS ai_signal, p.up_probability, p.excess_return, p.actual_return, p.market_return,
               s.company_name
        FROM battle_picks b
        JOIN predictions p ON p.id = b.prediction_id
        LEFT JOIN listed_stocks s ON s.code = b.code
        WHERE b.user_id = :u
        ORDER BY b.round_date ASC, b.id ASC
    """), {"u": user_id})
    duels = []
    for r in rows:
        d = dict(r._mapping)
        excess = None if d["excess_return"] is None else float(d["excess_return"])
        user_ok = is_pick_correct(d["pick"], excess)
        ai_ok = is_pick_correct(d["ai_signal"], excess)
        settled = user_ok is not None
        duels.append({
            "code": d["code"], "company_name": d["company_name"], "round_date": str(d["round_date"])[:10],
            "pick": d["pick"], "settled": settled,
            # 未確定の間は AI の予想を見せない
            "ai_signal": d["ai_signal"] if settled else None,
            "ai_up_probability": float(d["up_probability"]) if settled and d["up_probability"] is not None else None,
            "excess_return_pct": round(excess * 100, 2) if excess is not None else None,
            "user_correct": user_ok, "ai_correct": ai_ok if settled else None,
            "outcome": duel_outcome(user_ok, ai_ok),
        })
    return duels


def _summarize(duels: list[dict]) -> dict:
    settled = [d for d in duels if d["settled"]]
    n = len(settled)
    user_wins = sum(1 for d in settled if d["user_correct"])
    ai_wins = sum(1 for d in settled if d["ai_correct"])
    cur, best = streaks([bool(d["user_correct"]) for d in settled])
    rate = user_wins / n if n else 0.0
    return {
        "settled": n, "pending": len(duels) - n,
        "user_correct": user_wins, "user_win_rate": round(rate, 4) if n else None,
        "ai_correct": ai_wins, "ai_win_rate": round(ai_wins / n, 4) if n else None,
        "duel_wins": sum(1 for d in settled if d["outcome"] == "win"),
        "duel_losses": sum(1 for d in settled if d["outcome"] == "lose"),
        "duel_draws": sum(1 for d in settled if d["outcome"] == "draw"),
        "current_streak": cur, "best_streak": best,
        "title": title_for(n, rate, best),
        "title_needs": TITLE_MIN_PICKS,
    }


# ── エンドポイント ────────────────────────────────────────────────────────────

@router.get("/today")
async def get_today(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    rd = await _round_date(db)
    if rd is None:
        return {"round_date": None, "closed": True, "stocks": [], "answered": 0, "disclaimer": DISCLAIMER}
    stocks = await _today_round(db, rd)
    mine = await db.execute(text("""
        SELECT prediction_id, pick FROM battle_picks WHERE user_id = :u AND round_date = :d
    """), {"u": current_user.id, "d": rd})
    my_picks = {r[0]: r[1] for r in mine}
    # 出題日の結果が出た後は新しい予想を受け付けない（結果を見てから答えられてしまうため）
    closed = any(s["excess_return"] is not None for s in stocks)
    out = []
    for s in stocks:
        out.append({
            "code": s["Code"], "company_name": s["company_name"], "sector_code": s["sector_code"],
            **(await _prices(db, s["Code"])),
            "my_pick": my_picks.get(s["prediction_id"]),
        })
    return {
        "round_date": rd, "closed": closed, "stocks": out,
        "answered": len(my_picks), "round_size": len(out), "disclaimer": DISCLAIMER,
    }


@router.post("/pick", status_code=201)
async def post_pick(body: PickIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    rd = await _round_date(db)
    if rd is None:
        raise HTTPException(409, "出題がありません")
    stocks = await _today_round(db, rd)
    target = next((s for s in stocks if s["Code"] == body.code), None)
    if target is None:
        raise HTTPException(404, "この銘柄は今日の出題に含まれていません")
    if any(s["excess_return"] is not None for s in stocks):
        raise HTTPException(409, "今日の出題は締め切られました")
    db.add(BattlePick(user_id=current_user.id, prediction_id=target["prediction_id"],
                      code=body.code, round_date=rd, pick=body.pick))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "この銘柄にはもう回答済みです（変更できません）")
    return {"code": body.code, "pick": body.pick, "round_date": rd}


@router.get("/me")
async def get_me(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    duels = await _my_duels(db, current_user.id)
    recent = list(reversed(duels))[:30]
    return {"summary": _summarize(duels), "recent": recent, "handle": handle_for(current_user.id),
            "disclaimer": DISCLAIMER}


@router.get("/leaderboard")
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    key = cache_key("battle", "leaderboard")
    cached = await cache_get(key)
    if cached is not None:
        return cached
    rows = await db.execute(text("""
        SELECT b.user_id, b.pick, p.excess_return, b.round_date, b.id AS pick_id
        FROM battle_picks b JOIN predictions p ON p.id = b.prediction_id
        WHERE p.excess_return IS NOT NULL
        ORDER BY b.round_date ASC, b.id ASC
    """))
    per_user: dict[int, list[bool]] = {}
    for r in rows:
        ok = is_pick_correct(r[1], float(r[2]))
        per_user.setdefault(r[0], []).append(bool(ok))
    board = []
    for uid, results in per_user.items():
        n = len(results)
        if n < LEADERBOARD_MIN_PICKS:
            continue
        wins = sum(results)
        cur, best = streaks(results)
        board.append({"user_id": uid, "handle": handle_for(uid), "settled": n, "wins": wins,
                      "win_rate": round(wins / n, 4), "current_streak": cur, "best_streak": best,
                      "score": wilson_lower(wins, n)})
    board.sort(key=lambda x: (-x["score"], -x["settled"]))
    board = board[:LEADERBOARD_SIZE]
    for i, b in enumerate(board, 1):
        b["rank"] = i
    result = {"entries": [{k: v for k, v in b.items() if k not in ("score", "user_id")} for b in board],
              "min_picks": LEADERBOARD_MIN_PICKS,
              "note": "的中率の信頼区間の下限で順位を決めています（少ない対戦数での偶然の高勝率が上位に来ないように）。",
              "disclaimer": DISCLAIMER}
    await cache_set(key, result, CACHE_TTL)
    return result
