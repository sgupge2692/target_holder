-- TimescaleDB拡張の有効化
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 上場銘柄テーブル
CREATE TABLE IF NOT EXISTS listed_stocks (
    code VARCHAR(10) PRIMARY KEY,
    company_name VARCHAR(255),
    market_code VARCHAR(10),
    sector_code VARCHAR(10),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 日足データテーブル（時系列）
CREATE TABLE IF NOT EXISTS daily_quotes (
    id SERIAL,
    "Code" VARCHAR(10) NOT NULL,
    "Date" DATE NOT NULL,
    "Open" NUMERIC,
    "High" NUMERIC,
    "Low" NUMERIC,
    "Close" NUMERIC,
    "Volume" BIGINT,
    "AdjustmentFactor" NUMERIC,
    "AdjustmentOpen" NUMERIC,
    "AdjustmentHigh" NUMERIC,
    "AdjustmentLow" NUMERIC,
    "AdjustmentClose" NUMERIC,
    "AdjustmentVolume" BIGINT,
    PRIMARY KEY ("Code", "Date")
);

-- TimescaleDBのハイパーテーブルに変換
SELECT create_hypertable('daily_quotes', 'Date', if_not_exists => TRUE);

-- 特徴量テーブル
CREATE TABLE IF NOT EXISTS features (
    "Code" VARCHAR(10) NOT NULL,
    "Date" DATE NOT NULL,
    ma5_deviation NUMERIC,
    ma25_deviation NUMERIC,
    ma75_deviation NUMERIC,
    golden_cross INTEGER,
    dead_cross INTEGER,
    bb_percent_b NUMERIC,
    bb_width NUMERIC,
    rsi NUMERIC,
    macd_diff NUMERIC,
    volume_ratio NUMERIC,
    price_up_vol_up INTEGER,
    body_ratio NUMERIC,
    upper_shadow NUMERIC,
    lower_shadow NUMERIC,
    next_return NUMERIC,
    label INTEGER,
    PRIMARY KEY ("Code", "Date")
);

-- 予測結果テーブル
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    "Code" VARCHAR(10) NOT NULL,
    "Date" DATE NOT NULL,
    up_probability NUMERIC NOT NULL,
    signal VARCHAR(10) NOT NULL,
    predicted_at TIMESTAMP DEFAULT NOW(),
    actual_return NUMERIC,  -- 後から実績を記録
    is_correct BOOLEAN      -- 的中フラグ
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_daily_quotes_code ON daily_quotes ("Code");
CREATE INDEX IF NOT EXISTS idx_features_code ON features ("Code");
CREATE INDEX IF NOT EXISTS idx_predictions_code ON predictions ("Code");
CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions ("Date");
