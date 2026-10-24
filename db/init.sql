-- TimescaleDB拡張の有効化
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 上場銘柄テーブル
CREATE TABLE IF NOT EXISTS listed_stocks (
    code        VARCHAR(10) PRIMARY KEY,
    company_name VARCHAR(255),
    market_code VARCHAR(10),
    sector_code  VARCHAR(10),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- 日足データテーブル（時系列）
-- 列名はfetch_data.pyのv2対応に合わせてsnake_case
CREATE TABLE IF NOT EXISTS daily_quotes (
    code            VARCHAR(10)  NOT NULL,
    date            DATE         NOT NULL,
    open            NUMERIC,
    high            NUMERIC,
    low             NUMERIC,
    close           NUMERIC,
    volume          BIGINT,
    turnover_value  NUMERIC,
    adj_open        NUMERIC,
    adj_high        NUMERIC,
    adj_low         NUMERIC,
    adj_close       NUMERIC,
    adj_volume      BIGINT,
    adj_factor      NUMERIC,
    PRIMARY KEY (code, date)
);

-- TimescaleDBのハイパーテーブルに変換（dateカラムで時系列分割）
SELECT create_hypertable('daily_quotes', 'date', if_not_exists => TRUE);

-- 特徴量テーブル
CREATE TABLE IF NOT EXISTS features (
    code            VARCHAR(10)  NOT NULL,
    date            DATE         NOT NULL,
    -- トレンド系
    ma5_deviation   NUMERIC,
    ma25_deviation  NUMERIC,
    ma75_deviation  NUMERIC,
    golden_cross    SMALLINT,
    dead_cross      SMALLINT,
    -- ボリンジャーバンド
    bb_percent_b    NUMERIC,
    bb_width        NUMERIC,
    -- オシレーター
    rsi             NUMERIC,
    macd_diff       NUMERIC,
    -- 出来高
    volume_ratio    NUMERIC,
    price_up_vol_up SMALLINT,
    -- ローソク足形状
    body_ratio      NUMERIC,
    upper_shadow    NUMERIC,
    lower_shadow    NUMERIC,
    -- リターン系（20日分のラグ）
    ret_lag_1  NUMERIC, ret_lag_2  NUMERIC, ret_lag_3  NUMERIC, ret_lag_4  NUMERIC,
    ret_lag_5  NUMERIC, ret_lag_6  NUMERIC, ret_lag_7  NUMERIC, ret_lag_8  NUMERIC,
    ret_lag_9  NUMERIC, ret_lag_10 NUMERIC, ret_lag_11 NUMERIC, ret_lag_12 NUMERIC,
    ret_lag_13 NUMERIC, ret_lag_14 NUMERIC, ret_lag_15 NUMERIC, ret_lag_16 NUMERIC,
    ret_lag_17 NUMERIC, ret_lag_18 NUMERIC, ret_lag_19 NUMERIC, ret_lag_20 NUMERIC,
    -- ラベル: 1=翌日+1%超, -1=翌日-1%超, 0=それ以外
    next_return NUMERIC,
    label       SMALLINT,
    PRIMARY KEY (code, date)
);

-- 予測結果テーブル
CREATE TABLE IF NOT EXISTS predictions (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(10)  NOT NULL,
    date            DATE         NOT NULL,
    up_probability  NUMERIC      NOT NULL,
    signal          VARCHAR(10)  NOT NULL,   -- 'UP', 'DOWN', 'HOLD'
    predicted_at    TIMESTAMP    DEFAULT NOW(),
    actual_return   NUMERIC,                 -- 後から実績を記録
    is_correct      BOOLEAN,                 -- 的中フラグ
    UNIQUE (code, date)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_daily_quotes_code ON daily_quotes (code);
CREATE INDEX IF NOT EXISTS idx_daily_quotes_date ON daily_quotes (date DESC);
CREATE INDEX IF NOT EXISTS idx_features_code     ON features (code);
CREATE INDEX IF NOT EXISTS idx_features_date     ON features (date DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_code  ON predictions (code);
CREATE INDEX IF NOT EXISTS idx_predictions_date  ON predictions (date DESC);
