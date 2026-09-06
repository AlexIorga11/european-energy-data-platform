SELECT
    energy.zone,
    energy.date_utc,
    locations.weather_location
FROM {{ ref('mart_energy_daily') }} AS energy
INNER JOIN {{ ref('dim_weather_location') }} AS locations
    ON energy.zone = locations.zone
WHERE NOT EXISTS (
    SELECT 1
    FROM {{ ref('mart_energy_weather_daily') }} AS combined
    WHERE combined.zone = energy.zone
        AND combined.date_utc = energy.date_utc
        AND combined.weather_location = locations.weather_location
)