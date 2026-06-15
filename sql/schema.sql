-- PostgreSQL schema for the relative-performance scorer.

CREATE TABLE IF NOT EXISTS securities (
    symbol    TEXT PRIMARY KEY,
    name      TEXT,
    sector    TEXT,
    industry  TEXT
);

CREATE TABLE IF NOT EXISTS prices (
    symbol      TEXT NOT NULL REFERENCES securities(symbol),
    trade_date  DATE NOT NULL,
    close       NUMERIC,
    adj_close   NUMERIC,
    PRIMARY KEY (symbol, trade_date)
);

-- Speeds up the as-of (<= date) look-up used for non-trading dates.
CREATE INDEX IF NOT EXISTS idx_prices_symbol_date
    ON prices (symbol, trade_date DESC);

CREATE TABLE IF NOT EXISTS custom_groups (
    group_name  TEXT NOT NULL,
    symbol      TEXT NOT NULL REFERENCES securities(symbol),
    PRIMARY KEY (group_name, symbol)
);

-- Example as-of price query (most recent row on/before a date, within window):
--   SELECT adj_close FROM prices
--   WHERE symbol = 'AAPL' AND trade_date <= '2024-03-31'
--     AND trade_date >= '2024-03-31'::date - 7
--   ORDER BY trade_date DESC LIMIT 1;
