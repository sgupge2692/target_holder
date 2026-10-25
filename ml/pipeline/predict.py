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
    "ma5_deviation", "ma25_deviation", "ma75_deviation",
    "golden_cross", "dead_cross",
    "bb_percent_b", "bb_width",
    "rsi", "macd_diff",
    "volume_ratio", "price_up_vol_up",
    "body_ratio", "upper_shadow", "lower_shadow",
] + [f"return_lag{i}" for i in range(1, 21)]

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
}

CONFIDENCE_THRESHOLD = 0.60


def get_top_features(model, feature_values: dict, n: int = 5) -> list[dict]:
    """LightGBM の feature importance 上位 n 件と実際の値を返す"""
    importances = model.feature_importances_
    ranked = sorted(
        zip(FEATURE_COLS, importances, [feature_values.get(f) for f in FEATURE_COLS]),
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


def build_prompt(code: str, signal: str, up_prob: float, top_features: list[dict]) -> str:
    direction = "上昇" if signal == "UP" else "下落"
    feat_lines = "\n".join(
        f"  - {f['label']}（{f['name']}）: {f['value']:.4f}" for f in top_features
    )
    return f"""あなたは株式テクニカル分析の専門家です。
以下の情報をもとに、銘柄 {code} の翌日予測シグナル（{direction}）の理由を
投資家向けに簡潔な日本語で説明してください。

予測シグナル: {signal}（{direction}予測）
上昇確率: {up_prob:.1%}

モデルが重視した主要指標（上位5件）:
{feat_lines}

以下の JSON 形式のみで回答してください（他のテキスト不要）:
{{
  "reason": "50文字以内の簡潔な理由",
  "key_indicators": ["指標1の解説（15字以内）", "指標2の解説（15字以内）"]
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


def main():
    engine = create_engine(DATABASE_URL)

    model = joblib.load(f"{MODEL_DIR}/lgbm_model.pkl")
    scaler = joblib.load(f"{MODEL_DIR}/scaler.pkl")

    # 最新の特徴量を取得
    df = pd.read_sql(
        'SELECT * FROM features ORDER BY "Date" DESC LIMIT 10000',
        engine,
    )

    # 各銘柄の最新行のみ取得
    latest = df.sort_values("Date").groupby("Code").last().reset_index()

    X = latest[FEATURE_COLS].replace([np.inf, -np.inf], np.nan)
    valid_idx = X.dropna().index
    X_valid = X.loc[valid_idx]
    X_scaled = scaler.transform(X_valid)

    proba = model.predict_proba(X_scaled)
    latest_valid = latest.loc[valid_idx].copy()
    latest_valid["up_probability"] = proba[:, 1]
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
            feat_values = {f: row[f] for f in FEATURE_COLS if f in row}
            top_feats = get_top_features(model, feat_values)
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

    up_count = (signals["signal"] == "UP").sum()
    down_count = (signals["signal"] == "DOWN").sum()
    print(f"Saved {len(signals)} signals (UP: {up_count}, DOWN: {down_count})")
    if OPENAI_API_KEY:
        print("LLM explanations generated.")
    else:
        print("OPENAI_API_KEY not set — skipped LLM explanations.")


if __name__ == "__main__":
    main()
