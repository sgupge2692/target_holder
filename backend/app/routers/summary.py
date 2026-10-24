"""
四季報 LLM 要約エンドポイント

GET  /api/summary/{code}           - キャッシュ済み要約を返す（未生成なら 404）
POST /api/summary/{code}           - テキストを受け取り要約を生成・保存（認証必須）
POST /api/summary/{code}/regenerate - 強制再生成（Pro のみ）

料金:
  - 無料: 要約の閲覧のみ可（overview のみ）
  - Pro : 全フィールド + 再生成 + テキスト貼り付け生成
"""
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from openai import AsyncOpenAI

from app.auth import get_current_user, require_pro
from app.database import get_db
from app.models import User
from app.config import settings

router = APIRouter(prefix="/api/summary", tags=["summary"])

OPENAI_MODEL = "gpt-4o-mini"
CURRENT_YEAR_LABEL = f"{datetime.now().year}秋"  # ラベル例: "2026秋"


# ── スキーマ ──────────────────────────────────────────────────

class SummaryResponse(BaseModel):
    code: str
    year_label: str
    overview: Optional[str]
    performance: Optional[str]
    risks: Optional[str]
    model: Optional[str]
    created_at: str
    plan: str  # ビューアのプラン（フロント分岐用）


class GenerateRequest(BaseModel):
    text: str          # 四季報テキスト（コピペ or HTML から抽出）
    year_label: str = CURRENT_YEAR_LABEL


# ── LLM 呼び出し ──────────────────────────────────────────────

SYSTEM_PROMPT = """あなたは株式投資アナリストです。
与えられた四季報テキストから以下の3項目を簡潔に抽出してください。
必ず JSON で返答してください（マークダウン不要）。

{
  "overview":     "会社概要・事業内容（2〜3文）",
  "performance":  "直近決算・来期予想・業績トレンド（2〜3文）",
  "risks":        "リスク・懸念点・競合状況（1〜2文）"
}
"""


async def call_openai(text: str) -> dict:
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OpenAI API キーが未設定です")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"以下の四季報テキストを解析してください:\n\n{text[:6000]}"},
        ],
        temperature=0.2,
        max_tokens=600,
    )
    import json
    return json.loads(response.choices[0].message.content)


# ── エンドポイント ────────────────────────────────────────────

@router.get("/{code}", response_model=SummaryResponse)
async def get_summary(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """キャッシュ済み要約を返す。無料プランは overview のみ。"""
    row = await db.execute(text("""
        SELECT code, year_label, overview, performance, risks, model,
               created_at::text
        FROM summaries
        WHERE code = :code
        ORDER BY created_at DESC
        LIMIT 1
    """), {"code": code})
    summary = row.fetchone()

    if not summary:
        raise HTTPException(status_code=404, detail="要約がまだ生成されていません")

    data = dict(summary._mapping)
    is_pro = current_user.plan == "pro"

    # 無料プランは performance / risks をマスク
    if not is_pro:
        data["performance"] = None
        data["risks"]       = None

    data["plan"] = current_user.plan
    return SummaryResponse(**data)


@router.post("/{code}", response_model=SummaryResponse)
async def generate_summary(
    code: str,
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    四季報テキストから LLM 要約を生成して保存。
    同一 code × year_label が既にあれば返すだけ（再生成は /regenerate）。
    """
    # 既存キャッシュを確認
    existing = await db.execute(text("""
        SELECT code, year_label, overview, performance, risks, model, created_at::text
        FROM summaries
        WHERE code = :code AND year_label = :year
        LIMIT 1
    """), {"code": code, "year": body.year_label})
    cached = existing.fetchone()
    if cached:
        data = dict(cached._mapping)
        data["plan"] = current_user.plan
        return SummaryResponse(**data)

    # 生成
    result = await call_openai(body.text)

    await db.execute(text("""
        INSERT INTO summaries (code, year_label, overview, performance, risks, raw_text, model)
        VALUES (:code, :year, :overview, :performance, :risks, :raw_text, :model)
        ON CONFLICT (code, year_label) DO UPDATE
        SET overview=EXCLUDED.overview, performance=EXCLUDED.performance,
            risks=EXCLUDED.risks, raw_text=EXCLUDED.raw_text, model=EXCLUDED.model,
            created_at=NOW()
    """), {
        "code":        code,
        "year":        body.year_label,
        "overview":    result.get("overview"),
        "performance": result.get("performance"),
        "risks":       result.get("risks"),
        "raw_text":    body.text[:8000],
        "model":       OPENAI_MODEL,
    })
    await db.commit()

    row = await db.execute(text("""
        SELECT code, year_label, overview, performance, risks, model, created_at::text
        FROM summaries WHERE code = :code AND year_label = :year
    """), {"code": code, "year": body.year_label})
    data = dict(row.fetchone()._mapping)
    data["plan"] = current_user.plan
    return SummaryResponse(**data)


@router.post("/{code}/regenerate", response_model=SummaryResponse)
async def regenerate_summary(
    code: str,
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_pro),  # Pro のみ
):
    """強制再生成（Pro 専用）"""
    result = await call_openai(body.text)

    await db.execute(text("""
        INSERT INTO summaries (code, year_label, overview, performance, risks, raw_text, model)
        VALUES (:code, :year, :overview, :performance, :risks, :raw_text, :model)
        ON CONFLICT (code, year_label) DO UPDATE
        SET overview=EXCLUDED.overview, performance=EXCLUDED.performance,
            risks=EXCLUDED.risks, raw_text=EXCLUDED.raw_text, model=EXCLUDED.model,
            created_at=NOW()
    """), {
        "code":        code,
        "year":        body.year_label,
        "overview":    result.get("overview"),
        "performance": result.get("performance"),
        "risks":       result.get("risks"),
        "raw_text":    body.text[:8000],
        "model":       OPENAI_MODEL,
    })
    await db.commit()

    row = await db.execute(text("""
        SELECT code, year_label, overview, performance, risks, model, created_at::text
        FROM summaries WHERE code = :code AND year_label = :year
    """), {"code": code, "year": body.year_label})
    data = dict(row.fetchone()._mapping)
    data["plan"] = "pro"
    return SummaryResponse(**data)
