{{ config(materialized='table') }}

WITH weather AS (
    SELECT
        location,
        (interval_start AT TIME ZONE 'UTC')::date AS date_utc,
        temperature_c,
        wind_speed_kmh
    FROM {{ source('open_meteo', 'weather_hourly') }}
)

SELECT
    location,
    date_utc,
    COUNT(*) AS interval_count,
    ROUND(AVG(temperature_c), 2) AS avg_temperature_c,
    MIN(temperature_c) AS min_temperature_c,
    MAX(temperature_c) AS max_temperature_c,
    ROUND(AVG(wind_speed_kmh), 2) AS avg_wind_speed_kmh,
    MAX(wind_speed_kmh) AS max_wind_speed_kmh
FROM weather
GROUP BY
    location,
    date_utc