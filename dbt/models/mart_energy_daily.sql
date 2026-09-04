{{ config(materialized='table') }}

WITH prices AS (
    SELECT
        zone,
        (interval_start AT TIME ZONE 'UTC')::date AS date_utc,
        price_eur_per_mwh
    FROM {{ source('energy_charts', 'energy_prices') }}
)

SELECT
    zone,
    date_utc,
    COUNT(*) AS interval_count,
    ROUND(AVG(price_eur_per_mwh), 4) AS avg_price_eur_per_mwh,
    MIN(price_eur_per_mwh) AS min_price_eur_per_mwh,
    MAX(price_eur_per_mwh) AS max_price_eur_per_mwh
FROM prices
GROUP BY
    zone,
    date_utc