{{ config(materialized='table') }}

{% set locations = var('weather_locations') %}

{% for location_id, location in locations.items() if location['energy_zone'] is not none %}
SELECT
    '{{ location_id | replace("'", "''") }}'::text AS weather_location,
    '{{ location["name"] | replace("'", "''") }}'::text AS location_name,
    '{{ location["energy_zone"] | replace("'", "''") }}'::text AS zone
{% if not loop.last %}UNION ALL{% endif %}
{% endfor %}