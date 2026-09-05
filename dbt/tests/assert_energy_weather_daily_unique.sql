SELECT
    zone,
    date_utc,
    weather_location,
    COUNT(*) AS row_count
FROM {{ ref('mart_energy_weather_daily') }}
GROUP BY
    zone,
    date_utc,
    weather_location
HAVING COUNT(*) > 1