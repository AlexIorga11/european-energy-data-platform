SELECT
    energy.zone,
    energy.date_utc
FROM {{ ref('mart_energy_daily') }} AS energy
WHERE energy.zone = 'DE-LU'
    AND NOT EXISTS (
        SELECT 1
        FROM {{ ref('mart_energy_weather_daily') }} AS combined
        WHERE combined.zone = energy.zone
            AND combined.date_utc = energy.date_utc
            AND combined.weather_location = 'berlin'
    )