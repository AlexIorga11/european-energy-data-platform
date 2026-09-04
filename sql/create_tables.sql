CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.energy_prices (
    zone TEXT NOT NULL,
    interval_start TIMESTAMPTZ NOT NULL,
    price_eur_per_mwh NUMERIC(12, 4) NOT NULL,
    source_file TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (zone, interval_start)
);