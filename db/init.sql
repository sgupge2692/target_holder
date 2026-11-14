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
    market_return NUMERIC,  -- 同期間の全銘柄リターン中央値
    excess_return NUMERIC,  -- actual_return - market_return
    is_correct BOOLEAN      -- 的中フラグ（市場超過の符号で判定）
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_daily_quotes_code ON daily_quotes ("Code");
CREATE INDEX IF NOT EXISTS idx_features_code ON features ("Code");
CREATE INDEX IF NOT EXISTS idx_predictions_code ON predictions ("Code");
CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions ("Date");

-- ニュース記事（毎日収集して蓄積する。ニュース特徴量は「その時点で見られた記事」だけで作る）
CREATE TABLE IF NOT EXISTS news_articles (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) NOT NULL,
    url_hash VARCHAR(32) NOT NULL,
    title TEXT NOT NULL,
    source VARCHAR(30),
    published_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    urgency REAL NOT NULL DEFAULT 0,
    UNIQUE (code, url_hash)
);
CREATE INDEX IF NOT EXISTS idx_news_articles_code_seen ON news_articles (code, first_seen_at);
