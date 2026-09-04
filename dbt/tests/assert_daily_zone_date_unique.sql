SELECT
    zone,
    date_utc,
    COUNT(*) AS row_count
FROM {{ ref('mart_energy_daily') }}
GROUP BY
    zone,
    date_utc
HAVING COUNT(*) > 1