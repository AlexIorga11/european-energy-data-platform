SELECT *
FROM {{ ref('mart_energy_weather_daily') }}
WHERE has_weather_data IS NULL
    OR (
        has_weather_data = TRUE
        AND (
            weather_interval_count IS NULL
            OR avg_temperature_c IS NULL
            OR min_temperature_c IS NULL
            OR max_temperature_c IS NULL
            OR avg_wind_speed_kmh IS NULL
            OR max_wind_speed_kmh IS NULL
        )
    )
    OR (
        has_weather_data = FALSE
        AND (
            weather_interval_count IS NOT NULL
            OR avg_temperature_c IS NOT NULL
            OR min_temperature_c IS NOT NULL
            OR max_temperature_c IS NOT NULL
            OR avg_wind_speed_kmh IS NOT NULL
            OR max_wind_speed_kmh IS NOT NULL
        )
    )