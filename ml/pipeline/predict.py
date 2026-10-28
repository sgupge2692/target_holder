"""
翌日騰落予測を実行してDBに保存するスクリプト
LightGBM の feature importance を元に gpt-4o-mini でシグナル理由を生成する
"""
import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_DIR = "/app/models"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

FEATURE_COLS = [
    # 既存
    "ma5_deviation", "ma25_deviation", "ma75_deviation",
    "golden_cross", "dead_cross",
    "bb_percent_b", "bb_width",
    "rsi", "macd_diff",
    "volume_ratio", "price_up_vol_up",
    "body_ratio", "upper_shadow", "lower_shadow",
    # ラグリターン
    *[f"return_lag{i}" for i in range(1, 21)],
    # 新規追加 v2
    "vwap_deviation",
    "atr_ratio",
    "obv_trend",
    "volume_momentum",
    "roc_5", "roc_20",
    "williams_r",
    "stoch_k", "stoch_d", "stoch_diff",
]

# 説明に使う特徴量の日本語名
FEATURE_LABELS = {
    "ma5_deviation":   "MA5乖離率",
    "ma25_deviation":  "MA25乖離率",
    "ma75_deviation":  "MA75乖離率",
    "golden_cross":    "ゴールデンクロス",
    "dead_cross":      "デッドクロス",
    "bb_percent_b":    "ボリンジャー%B",
    "bb_width":        "BB幅",
    "rsi":             "RSI",
    "macd_diff":       "MACDヒストグラム",
    "volume_ratio":    "出来高比率",
    "price_up_vol_up": "価格上昇×出来高増",
    "body_ratio":      "実体比率",
    "upper_shadow":    "上ヒゲ比率",
    "lower_shadow":    "下ヒゲ比率",
    # v2
    "vwap_deviation":  "VWAP乖離率",
    "atr_ratio":       "ATR比率（ボラ）",
    "obv_trend":       "OBVトレンド",
    "volume_momentum": "出来高モメンタム",
    "roc_5":           "価格RoC(5日)",
    "roc_20":          "価格RoC(20日)",
    "williams_r":      "Williams %R",
    "stoch_k":         "ストキャス%K",
    "stoch_d":         "ストキャス%D",
    "stoch_diff":      "ストキャスKD差",
    # v3 カレンダー
    "day_of_week":     "曜日",
    "is_monday":       "月曜フラグ",
    "is_friday":       "金曜フラグ",
    "month":           "月",
    "quarter":         "四半期",
    "is_month_end":    "月末フラグ",
    "is_month_start":  "月初フラグ",
    # v3 相対特徴量
    "market_relative_return": "市場相対リターン",
    "market_relative_rsi":    "市場相対RSI",
    "sector_relative_return": "セクター相対リターン",
    "sector_relative_rsi":    "セクター相対RSI",
    "sector_relative_ma5":    "セクター相対MA5",
    # v4 ニュースセンチメント
    "news_sentiment":         "ニュースセンチメント",
    "news_pos_count":         "ポジニュース件数",
    "news_neg_count":         "ネガニュース件数",
    "news_article_count":     "ニュース取得件数",
    # v5 ギャップ・ボラ・価格位置
    "gap_up":                 "ギャップアップ率",
    "gap_down":               "ギャップダウン率",
    "gap":                    "寄り付きギャップ",
    "volume_spike":           "出来高急増フラグ",
    "volume_spike_ratio":     "出来高急増σ倍率",
    "volatility_5d":          "ボラティリティ5日",
    "volatility_20d":         "ボラティリティ20日",
    "dist_from_high_52w":     "52週高値からの乖離",
    "dist_from_low_52w":      "52週安値からの乖離",
    "price_position_52w":     "52週レンジ位置",
    "streak_up":              "連続上昇日数",
    "streak_down":            "連続下落日数",
    "new_high_20d":           "20日高値更新",
    "new_low_20d":            "20日安値更新",
    "new_high_60d":           "60日高値更新",
    "new_low_60d":            "60日安値更新",
}

CONFIDENCE_THRESHOLD = 0.60


def get_top_features(model, feature_values: dict, n: int = 5, feat_cols: list | None = None) -> list[dict]:
    """LightGBM の feature importance 上位 n 件と実際の値を返す"""
    cols = feat_cols or FEATURE_COLS
    importances = model.feature_importances_
    ranked = sorted(
        zip(cols, importances, [feature_values.get(f) for f in cols]),
        key=lambda x: x[1],
        reverse=True,
    )
    result = []
    for name, imp, val in ranked[:n]:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            continue
        label = FEATURE_LABELS.get(name, name)
        result.append({"name": name, "label": label, "importance": float(imp), "value": float(val)})
    return result


def _fmt_feature_value(name: str, val: float) -> str:
    """特徴量の値を分かりやすく整形する"""
    pct_features = {
        "ma5_deviation", "ma25_deviation", "ma75_deviation",
        "bb_percent_b", "vwap_deviation", "gap_up", "gap_down", "gap",
        "volatility_5d", "volatility_20d",
        "dist_from_high_52w", "dist_from_low_52w", "price_position_52w",
        "roc_5", "roc_20",
    }
    if name in pct_features:
        return f"{val*100:+.2f}%"
    if name in {"rsi", "stoch_k", "stoch_d"}:
        return f"{val:.1f}"
    if name in {"golden_cross", "dead_cross", "volume_spike", "is_monday", "is_friday",
                "is_month_end", "is_month_start", "new_high_20d", "new_low_20d",
                "new_high_60d", "new_low_60d", "price_up_vol_up"}:
        return "あり" if val == 1 else "なし"
    if name in {"streak_up", "streak_down"}:
        return f"{int(val)}日連続"
    if name in {"volume_ratio", "volume_spike_ratio"}:
        return f"{val:.2f}倍"
    return f"{val:.4f}"


def build_prompt(code: str, signal: str, up_prob: float, top_features: list[dict]) -> str:
    direction = "上昇" if signal == "UP" else "下落"
    feat_lines = "\n".join(
        f"  - {f['label']}: {_fmt_feature_value(f['name'], f['value'])}" for f in top_features
    )
    return f"""あなたは株式テクニカル分析の専門家です。
以下の情報をもとに、銘柄 {code} の翌日予測シグナル（{direction}）の理由を
個人投資家向けに分かりやすい日本語で説明してください。

予測シグナル: {signal}（{direction}予測）
上昇確率: {up_prob:.1%}

モデルが重視した主要指標（上位5件）:
{feat_lines}

指示:
- 数字は具体的に引用してください（例: RSI 28.3 → 売られ過ぎ水準）
- 専門用語は簡単な補足をつけてください
- {direction}の根拠を明確に述べてください

以下の JSON 形式のみで回答してください（他のテキスト不要）:
{{
  "reason": "60文字以内の簡潔な理由（具体的な数値を含む）",
  "key_indicators": ["指標1の解説（20字以内）", "指標2の解説（20字以内）", "指標3の解説（20字以内）"]
}}"""


def generate_explanation(code: str, signal: str, up_prob: float, top_features: list[dict]) -> dict:
    """gpt-4o-mini でシグナル説明を生成する"""
    if not OPENAI_API_KEY:
        return {"reason": "説明生成にはOPENAI_API_KEYが必要です", "key_indicators": []}

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = build_prompt(code, signal, up_prob, top_features)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"LLM explanation failed for {code}: {e}")
        return {"reason": f"生成失敗: {e}", "key_indicators": []}


def load_models():
    """LightGBM（必須）と XGBoost（任意）をロード。アンサンブル重みも返す。"""
    lgbm   = joblib.load(f"{MODEL_DIR}/lgbm_model.pkl")
    scaler = joblib.load(f"{MODEL_DIR}/scaler.pkl")

    # feature_cols.pkl があれば使用（v3以降）、なければデフォルト
    feat_cols_path = f"{MODEL_DIR}/feature_cols.pkl"
    feat_cols = joblib.load(feat_cols_path) if os.path.exists(feat_cols_path) else FEATURE_COLS

    xgb     = None
    weights = {"lgbm": 1.0, "xgb": 0.0}
    ew_path = f"{MODEL_DIR}/ensemble_weights.pkl"
    xgb_path = f"{MODEL_DIR}/xgb_model.pkl"
    if os.path.exists(ew_path) and os.path.exists(xgb_path):
        try:
            xgb     = joblib.load(xgb_path)
            weights = joblib.load(ew_path)
            print(f"Ensemble mode — LGBM: {weights['lgbm']:.3f}  XGB: {weights['xgb']:.3f}")
        except Exception as e:
            print(f"XGBoost load failed ({e}), LGBM only.")

    return lgbm, xgb, scaler, weights, feat_cols


def main():
    engine = create_engine(DATABASE_URL)

    lgbm, xgb, scaler, weights, feat_cols = load_models()

    # 最新の特徴量を取得
    df = pd.read_sql(
        'SELECT * FROM features ORDER BY "Date" DESC LIMIT 10000',
        engine,
    )

    # 各銘柄の最新行のみ取得
    latest = df.sort_values("Date").groupby("Code").last().reset_index()

    available = [c for c in feat_cols if c in latest.columns]
    X = latest[available].replace([np.inf, -np.inf], np.nan)
    valid_idx = X.dropna().index
    X_valid = X.loc[valid_idx]
    X_scaled = scaler.transform(X_valid)

    # アンサンブル or 単体
    lgbm_prob = lgbm.predict_proba(X_scaled)[:, 1]
    if xgb is not None:
        xgb_prob = xgb.predict_proba(X_scaled)[:, 1]
        up_prob  = weights["lgbm"] * lgbm_prob + weights["xgb"] * xgb_prob
    else:
        up_prob = lgbm_prob

    proba = np.column_stack([1 - up_prob, up_prob])
    latest_valid = latest.loc[valid_idx].copy()
    latest_valid["up_probability"] = up_prob
    latest_valid["signal"] = np.where(
        latest_valid["up_probability"] >= CONFIDENCE_THRESHOLD, "UP",
        np.where(latest_valid["up_probability"] <= (1 - CONFIDENCE_THRESHOLD), "DOWN", "NEUTRAL"),
    )
    latest_valid["predicted_at"] = datetime.now()

    # シグナルのみ対象
    signals = latest_valid[latest_valid["signal"] != "NEUTRAL"].copy()

    # LLM で説明生成（UP/DOWN のみ、バッチ処理）
    explanations = []
    key_factors_list = []
    if OPENAI_API_KEY:
        print(f"Generating LLM explanations for {len(signals)} signals...")
        for _, row in signals.iterrows():
            feat_values = {f: row[f] for f in feat_cols if f in row}
            top_feats = get_top_features(lgbm, feat_values, feat_cols=feat_cols)
            result = generate_explanation(row["Code"], row["signal"], row["up_probability"], top_feats)
            explanations.append(result.get("reason", ""))
            key_factors_list.append(json.dumps(result.get("key_indicators", []), ensure_ascii=False))
    else:
        explanations = [""] * len(signals)
        key_factors_list = ["[]"] * len(signals)

    signals = signals.copy()
    signals["explanation"] = explanations
    signals["key_factors"] = key_factors_list

    # DB に保存
    out = signals[["Code", "Date", "up_probability", "signal", "predicted_at", "explanation", "key_factors"]]
    out.to_sql("predictions", engine, if_exists="append", index=False)

    up_count = int((signals["signal"] == "UP").sum())
    down_count = int((signals["signal"] == "DOWN").sum())
    print(f"Saved {len(signals)} signals (UP: {up_count}, DOWN: {down_count})")
    if OPENAI_API_KEY:
        print("LLM explanations generated.")
    else:
        print("OPENAI_API_KEY not set — skipped LLM explanations.")

    # ── Prometheus Push Gateway にメトリクスを送信（任意）──────────────────
    _push_metrics(up_count, down_count)


def _push_metrics(up_count: int, down_count: int) -> None:
    """Prometheus Push Gateway が設定されていれば生成シグナル数を送信する"""
    push_gw = os.getenv("PROMETHEUS_PUSH_GATEWAY", "")
    if not push_gw:
        return
    try:
        from prometheus_client import Counter, push_to_gateway, CollectorRegistry
        reg = CollectorRegistry()
        c = Counter("ml_signals_generated_total", "Signals generated by ML pipeline",
                    ["signal_type"], registry=reg)
        c.labels(signal_type="UP")._value.set(up_count)
        c.labels(signal_type="DOWN")._value.set(down_count)
        push_to_gateway(push_gw, job="ml_predict", registry=reg)
        print(f"Pushed metrics to {push_gw}")
    except Exception as e:
        print(f"Prometheus push failed (non-fatal): {e}")


if __name__ == "__main__":
    main()
