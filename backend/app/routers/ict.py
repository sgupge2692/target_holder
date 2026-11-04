"""
ICT チャート分析 API
- POST /api/ict/{code}  : 銘柄コードの ICT 分析を実行（Pro 専用）
  - daily_quotes から OHLC を取得
  - matplotlib で週足・日足・短期日足チャートを生成
  - OpenAI Vision に ICT プロンプトを投げる
  - エントリー・SL・TP・根拠を JSON で返す
"""
import os
import io
import json
import base64
import logging
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from openai import AsyncOpenAI

from app.auth import get_current_user
from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ict", tags=["ict"])

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── デモ用モック分析（APIキー不要） ────────────────────────────────────────────
import random

def _mock_analysis(code: str, last_close: float, company_name: str) -> dict:
    """OpenAI キー未設定時のリアルなデモ分析データを生成"""
    rng = random.Random(hash(code) % 9999)
    is_buy = rng.random() > 0.4
    decision = "BUY" if is_buy else ("SELL" if rng.random() > 0.4 else "NO_TRADE")
    strength = rng.choice(["強", "中", "弱"])

    # 価格帯をリアルに
    pct_entry  = rng.uniform(0.001, 0.008)
    pct_sl     = rng.uniform(0.015, 0.030)
    pct_tp1    = rng.uniform(0.020, 0.040)
    pct_tp2    = rng.uniform(0.045, 0.080)

    if decision == "BUY":
        entry_price = round(last_close * (1 - pct_entry), 0)
        sl_price    = round(last_close * (1 - pct_sl), 0)
        tp1_price   = round(last_close * (1 + pct_tp1), 0)
        tp2_price   = round(last_close * (1 + pct_tp2), 0)
        rr1 = round(pct_tp1 / pct_sl, 1)
        rr2 = round(pct_tp2 / pct_sl, 1)
        structure = "上位足で高値切り上げ継続。直近 MSS（市場構造転換）が確認され、買い優位のバイアスが継続中。"
        dol = f"前週高値 ¥{round(last_close * (1 + pct_tp2 * 0.6)):,} 付近の BSL（Buy-Side Liquidity）が主要ターゲット。"
        area = "ディスカウント帯（レンジ下半分）からのリバウンド局面"
        entry_zone = f"日足 OB（Order Block）¥{entry_price:,.0f}〜¥{round(entry_price * 1.005):,.0f} ゾーン"
        entry_trigger = "日足終値で OB 上限を上抜け + 出来高増加を確認"
        sl_rationale = "OB 下限を終値で割り込んだ場合、シナリオ崩壊と判断"
        tp1_rationale = "直近スイング高値付近の FVG（Fair Value Gap）充填ゾーン"
        tp2_rationale = "上位足 DOL（流動性ターゲット）前週高値"
        confluences = [
            "HTF（週足）: 高値切り上げ継続で上昇トレンド構造を維持",
            f"MTF（日足）: ディスカウント帯 OB からの反発確認",
            "LTF（短期日足）: MSS 形成後の押し目待ち状態",
            "出来高: 直近 2 日間で 20 日平均の 1.8 倍に増加",
        ]
        invalidation = f"¥{sl_price:,.0f} を日足終値で下抜けた場合、下落トレンド転換の可能性。ポジション撤退。"
        warnings = ["重要指標発表日（翌週）はサイズ縮小を推奨", "エントリー前に出来高急増を確認すること"]
    elif decision == "SELL":
        entry_price = round(last_close * (1 + pct_entry), 0)
        sl_price    = round(last_close * (1 + pct_sl), 0)
        tp1_price   = round(last_close * (1 - pct_tp1), 0)
        tp2_price   = round(last_close * (1 - pct_tp2), 0)
        rr1 = round(pct_tp1 / pct_sl, 1)
        rr2 = round(pct_tp2 / pct_sl, 1)
        structure = "上位足で安値切り下げが発生。BOS（Break of Structure）後に戻り売り局面へ移行中。"
        dol = f"前週安値 ¥{round(last_close * (1 - pct_tp2 * 0.6)):,} 付近の SSL（Sell-Side Liquidity）をターゲット。"
        area = "プレミアム帯（レンジ上半分）での戻り売り局面"
        entry_zone = f"日足 Bearish OB ¥{entry_price:,.0f}〜¥{round(entry_price * 1.008):,.0f} ゾーン"
        entry_trigger = "日足終値で Bearish OB 下限を下抜け + 上ヒゲ確認"
        sl_rationale = "Bearish OB 上限を終値で上抜けた場合、反転シナリオへ切り替え"
        tp1_rationale = "直近スイング安値付近の IFVG（反転 FVG）サポートゾーン"
        tp2_rationale = "下位足 DOL（流動性ターゲット）前週安値"
        confluences = [
            "HTF（週足）: 安値切り下げで下降トレンド構造が確認済み",
            "MTF（日足）: プレミアム帯 Bearish OB でレジスタンス反応",
            "LTF（短期日足）: BOS 形成後の戻り売りエントリー待機中",
            "RSI: 60 超の過熱域からの下落サイン",
        ]
        invalidation = f"¥{sl_price:,.0f} を日足終値で上抜けた場合、上昇継続の可能性。即時撤退。"
        warnings = ["板が薄い時間帯のエントリーは避けること", "週またぎのポジション保有はリスク管理を厳格に"]
    else:
        entry_price = sl_price = tp1_price = tp2_price = None
        rr1 = rr2 = 0
        structure = "上位足・下位足で方向性が一致せず、横ばい相場が継続中。"
        dol = "明確な流動性ターゲットが確認できない。エッジのないレンジ相場。"
        area = "レンジ中央（Equilibrium）付近で方向感なし"
        entry_zone = "エントリー見送り"
        entry_trigger = "明確なセットアップ出現まで待機"
        sl_rationale = "エントリーなし"
        tp1_rationale = "エントリーなし"
        tp2_rationale = "エントリーなし"
        confluences = [
            "HTF・MTF でトレンド方向が一致しない",
            "レンジ中央付近で優位性が低い",
            "出来高が平均を下回りモメンタム欠如",
        ]
        invalidation = "明確な BOS または MSS が出現するまでウォッチリスト登録のみ推奨"
        warnings = ["強いセットアップが出るまで待機が最善", "焦ってのエントリーは損失の元"]

    return {
        "decision": decision,
        "decision_strength": strength,
        "current_price_area": area,
        "dol": dol,
        "structure": structure,
        "entry": {
            "price": entry_price,
            "zone": entry_zone,
            "trigger": entry_trigger,
        },
        "stop_loss": {
            "price": sl_price,
            "rationale": sl_rationale,
        },
        "take_profit_1": {
            "price": tp1_price,
            "rationale": tp1_rationale,
            "rr": f"{rr1}R",
        },
        "take_profit_2": {
            "price": tp2_price,
            "rationale": tp2_rationale,
            "rr": f"{rr2}R",
        },
        "key_confluences": confluences,
        "invalidation": invalidation,
        "risk_warnings": warnings,
        "_demo": True,  # デモデータであることを示すフラグ
    }


# ── チャート描画ユーティリティ ──────────────────────────────────────────────

def _draw_candlestick(ax, dates, opens, highs, lows, closes, title: str, color_up="#0d9488", color_down="#dc2626"):
    """シンプルなローソク足を描画（mplfinance 不使用でシンプルに）"""
    ax.set_facecolor("#0c1424")
    ax.set_title(title, color="#94a3b8", fontsize=9, pad=4)
    ax.tick_params(colors="#475569", labelsize=7)
    ax.spines[:].set_color("#1e293b")

    for i, (d, o, h, l, c) in enumerate(zip(dates, opens, highs, lows, closes)):
        color = color_up if c >= o else color_down
        # ローソク本体
        body_bottom = min(o, c)
        body_height = abs(c - o) if abs(c - o) > 0 else (h - l) * 0.001
        ax.bar(i, body_height, bottom=body_bottom, color=color, width=0.6, linewidth=0)
        # ヒゲ
        ax.plot([i, i], [l, h], color=color, linewidth=0.8, alpha=0.8)

    # 移動平均
    if len(closes) >= 20:
        ma20 = np.convolve(closes, np.ones(20) / 20, mode="valid")
        ax.plot(range(19, len(closes)), ma20, color="#f59e0b", linewidth=0.8, alpha=0.7, label="MA20")
    if len(closes) >= 5:
        ma5 = np.convolve(closes, np.ones(5) / 5, mode="valid")
        ax.plot(range(4, len(closes)), ma5, color="#60a5fa", linewidth=0.8, alpha=0.7, label="MA5")

    # X 軸ラベル（間引き）
    step = max(1, len(dates) // 6)
    ax.set_xticks(range(0, len(dates), step))
    ax.set_xticklabels([dates[i].strftime("%m/%d") for i in range(0, len(dates), step)],
                       color="#475569", fontsize=6, rotation=30)
    ax.set_xlim(-1, len(dates))


def _build_weekly(daily_rows) -> tuple[list, list, list, list, list]:
    """日足データを週足に集約"""
    from collections import defaultdict
    weekly: dict[tuple, list] = defaultdict(list)
    for row in daily_rows:
        d = row["Date"]
        iso = d.isocalendar()
        key = (iso.year, iso.week)
        weekly[key].append(row)

    result_dates, opens, highs, lows, closes = [], [], [], [], []
    for key in sorted(weekly.keys()):
        rows = weekly[key]
        result_dates.append(rows[0]["Date"])
        opens.append(float(rows[0]["AdjustmentOpen"] or rows[0]["Open"] or 0))
        highs.append(float(max(r["AdjustmentHigh"] or r["High"] or 0 for r in rows)))
        lows.append(float(min(r["AdjustmentLow"] or r["Low"] or 9999999 for r in rows)))
        closes.append(float(rows[-1]["AdjustmentClose"] or rows[-1]["Close"] or 0))
    return result_dates, opens, highs, lows, closes


def generate_charts(daily_rows: list[dict]) -> tuple[str, str, str]:
    """
    3種類のチャート画像を Base64 で返す
    - htf: 週足 (1年分)
    - mtf: 日足 (3ヶ月)
    - ltf: 日足ズーム (20日)
    """
    fig, axes = plt.subplots(3, 1, figsize=(10, 12), facecolor="#060b16")
    fig.tight_layout(pad=2.0)

    # HTF: 週足
    wdates, wo, wh, wl, wc = _build_weekly(daily_rows)
    _draw_candlestick(axes[0], wdates[-52:], wo[-52:], wh[-52:], wl[-52:], wc[-52:], "週足 (HTF — 1年)")

    # MTF: 日足 60日
    d60 = daily_rows[-60:]
    dates60 = [r["Date"] for r in d60]
    _draw_candlestick(
        axes[1],
        dates60,
        [float(r["AdjustmentOpen"] or r["Open"] or 0) for r in d60],
        [float(r["AdjustmentHigh"] or r["High"] or 0) for r in d60],
        [float(r["AdjustmentLow"] or r["Low"] or 0) for r in d60],
        [float(r["AdjustmentClose"] or r["Close"] or 0) for r in d60],
        "日足 (MTF — 60日)",
    )

    # LTF: 日足 20日
    d20 = daily_rows[-20:]
    dates20 = [r["Date"] for r in d20]
    _draw_candlestick(
        axes[2],
        dates20,
        [float(r["AdjustmentOpen"] or r["Open"] or 0) for r in d20],
        [float(r["AdjustmentHigh"] or r["High"] or 0) for r in d20],
        [float(r["AdjustmentLow"] or r["Low"] or 0) for r in d20],
        [float(r["AdjustmentClose"] or r["Close"] or 0) for r in d20],
        "日足ズーム (LTF — 20日)",
    )

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, facecolor="#060b16", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    combined_b64 = base64.b64encode(buf.read()).decode()
    return combined_b64


# ── ICT プロンプト ──────────────────────────────────────────────────────────

ICT_SYSTEM = """あなたはプロのトレーダーです。ICT（Inner Circle Trader）手法に精通しており、日本株の日足・週足チャートを分析して具体的なトレードプランを提示します。

## あなたのルール
- DOL (Draw on Liquidity): 価格が引き寄せられる流動性ターゲット（前高値・前安値・節目）を特定する
- AMD/PO3: Accumulation → Manipulation → Distribution の3段階を読む
- MSS/BOS: 市場構造の転換点と継続確認点を見極める
- FVG (Fair Value Gap): 未充填のギャップゾーンをサポート/レジスタンスとして使う
- プレミアム/ディスカウント: レンジの50%ラインより上（売り圧力）下（買い好機）を把握する

## 出力形式（必ず以下のJSONのみを返す）
{
  "decision": "BUY" | "SELL" | "NO_TRADE",
  "decision_strength": "強" | "中" | "弱",
  "current_price_area": "現在価格帯の説明（例: 前高値付近のプレミアム帯）",
  "dol": "流動性ターゲット（例: 前日高値 ¥3,850 付近のBSL）",
  "structure": "市場構造の説明（MSS/BOS/継続トレンドなど）",
  "entry": {
    "price": 数値 or null,
    "zone": "エントリーゾーンの説明",
    "trigger": "エントリー条件（例: 前高値を実体終値で上抜け）"
  },
  "stop_loss": {
    "price": 数値 or null,
    "rationale": "SL根拠"
  },
  "take_profit_1": {
    "price": 数値 or null,
    "rationale": "TP1根拠",
    "rr": "1R or 2R など"
  },
  "take_profit_2": {
    "price": 数値 or null,
    "rationale": "TP2根拠",
    "rr": "1R or 2R など"
  },
  "key_confluences": ["根拠1", "根拠2", "根拠3"],
  "invalidation": "このシナリオが崩れる条件",
  "risk_warnings": ["注意点1", "注意点2"]
}
"""

ICT_USER_TEMPLATE = """以下のチャートは {company_name}（{code}）の週足・日足・短期日足です。
最新の終値は ¥{last_close:.0f}（{last_date}）です。

ICT 手法で分析し、翌営業日のトレード戦略を JSON 形式で提示してください。"""


# ── エンドポイント ─────────────────────────────────────────────────────────

@router.post("/{code}")
async def run_ict_analysis(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.plan != "pro":
        raise HTTPException(status_code=403, detail="ICT分析はProプラン専用です")

    # OpenAI キー未設定 → デモモック
    if not OPENAI_API_KEY:
        chart_b64 = generate_charts(daily_rows) if len(daily_rows) >= 20 else ""
        analysis = _mock_analysis(code, last_close, company_name)
        return {
            "code": code,
            "company_name": company_name,
            "last_close": last_close,
            "last_date": last_date,
            "chart_image": f"data:image/png;base64,{chart_b64}" if chart_b64 else None,
            "analysis": analysis,
        }

    # 銘柄名取得
    stock_row = await db.execute(
        text("SELECT company_name FROM listed_stocks WHERE code = :code"), {"code": code}
    )
    stock = stock_row.fetchone()
    company_name = stock.company_name if stock else code

    # OHLC データ取得（約1年分）
    rows = await db.execute(
        text("""
            SELECT "Date", "Open", "High", "Low", "Close",
                   "AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose"
            FROM daily_quotes
            WHERE "Code" = :code
            ORDER BY "Date" ASC
            LIMIT 300
        """),
        {"code": code},
    )
    daily_rows = [dict(r._mapping) for r in rows]

    if len(daily_rows) < 20:
        raise HTTPException(status_code=404, detail=f"価格データが不足しています（{len(daily_rows)}日分）")

    last_row = daily_rows[-1]
    last_close = float(last_row["AdjustmentClose"] or last_row["Close"] or 0)
    last_date = str(last_row["Date"])

    # チャート画像生成
    try:
        chart_b64 = generate_charts(daily_rows)
    except Exception as e:
        logger.error(f"Chart generation failed for {code}: {e}")
        raise HTTPException(status_code=500, detail=f"チャート生成エラー: {e}")

    # OpenAI Vision 呼び出し
    try:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        user_msg = ICT_USER_TEMPLATE.format(
            company_name=company_name,
            code=code,
            last_close=last_close,
            last_date=last_date,
        )
        response = await client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1200,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": ICT_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_msg},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{chart_b64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
        )
        raw = response.choices[0].message.content or "{}"
        analysis = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error for {code}: {e}")
        raise HTTPException(status_code=500, detail="AI の出力が JSON ではありませんでした")
    except Exception as e:
        logger.error(f"OpenAI call failed for {code}: {e}")
        raise HTTPException(status_code=502, detail=f"AI 分析エラー: {e}")

    return {
        "code": code,
        "company_name": company_name,
        "last_close": last_close,
        "last_date": last_date,
        "chart_image": f"data:image/png;base64,{chart_b64}",
        "analysis": analysis,
    }
