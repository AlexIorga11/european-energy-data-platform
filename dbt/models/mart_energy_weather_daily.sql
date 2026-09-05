{{ config(materialized='table') }}

WITH energy AS (
    SELECT *
    FROM {{ ref('mart_energy_daily') }}
    WHERE zone = 'DE-LU'
),

weather AS (
    SELECT *
    FROM {{ ref('mart_weather_daily') }}
    WHERE location = 'berlin'
)

SELECT
    energy.zone,
    energy.date_utc,
    'berlin'::text AS weather_location,
    energy.interval_count AS price_interval_count,
    energy.avg_price_eur_per_mwh,
    energy.min_price_eur_per_mwh,
    energy.max_price_eur_per_mwh,
    weather.interval_count AS weather_interval_count,
    weather.avg_temperature_c,
    weather.min_temperature_c,
    weather.max_temperature_c,
    weather.avg_wind_speed_kmh,
    weather.max_wind_speed_kmh,
    weather.date_utc IS NOT NULL AS has_weather_data
FROM energy
LEFT JOIN weather
    ON energy.date_utc = weather.date_utc