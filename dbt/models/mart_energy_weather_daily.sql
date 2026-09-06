{{ config(materialized='table') }}

WITH energy AS (
    SELECT *
    FROM {{ ref('mart_energy_daily') }}
),

weather AS (
    SELECT *
    FROM {{ ref('mart_weather_daily') }}
),

locations AS (
    SELECT *
    FROM {{ ref('dim_weather_location') }}
)

SELECT
    energy.zone,
    energy.date_utc,
    locations.weather_location,
    locations.location_name,
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
INNER JOIN locations
    ON energy.zone = locations.zone
LEFT JOIN weather
    ON energy.date_utc = weather.date_utc
    AND locations.weather_location = weather.location