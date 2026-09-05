SELECT
    location,
    date_utc,
    COUNT(*) AS duplicate_count
FROM {{ ref('mart_weather_daily') }}
GROUP BY
    location,
    date_utc
HAVING COUNT(*) > 1