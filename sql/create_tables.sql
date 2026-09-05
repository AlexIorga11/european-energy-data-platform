CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.energy_prices (
    zone TEXT NOT NULL,
    interval_start TIMESTAMPTZ NOT NULL,
    price_eur_per_mwh NUMERIC(12, 4) NOT NULL,
    source_file TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (zone, interval_start)
);

CREATE TABLE IF NOT EXISTS staging.weather_hourly (
    location TEXT NOT NULL,
    interval_start TIMESTAMPTZ NOT NULL,
    temperature_c NUMERIC(6, 2) NOT NULL,
    wind_speed_kmh NUMERIC(7, 2) NOT NULL,
    latitude NUMERIC(9, 6) NOT NULL,
    longitude NUMERIC(9, 6) NOT NULL,
    source_file TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (location, interval_start),

    CONSTRAINT weather_wind_speed_non_negative
        CHECK (wind_speed_kmh >= 0),

    CONSTRAINT weather_latitude_valid
        CHECK (latitude BETWEEN -90 AND 90),

    CONSTRAINT weather_longitude_valid
        CHECK (longitude BETWEEN -180 AND 180)
);