import argparse
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from locations import DEFAULT_LOCATION, LOCATIONS, get_location
from validate_weather import (
    get_weather_file_path,
    load_and_validate_weather,
)


def get_database_connection() -> psycopg.Connection:
    project_dir = Path(__file__).resolve().parent
    load_dotenv(project_dir / ".env")

    password = os.getenv("POSTGRES_PASSWORD")

    if not password:
        raise RuntimeError(
            "POSTGRES_PASSWORD is missing from the environment"
        )

    return psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname="energy_warehouse",
        user="energy",
        password=password,
        connect_timeout=5,
    )


def build_weather_rows(
    data: dict,
    source_file: Path,
    location_id: str = DEFAULT_LOCATION,
) -> list[tuple]:
    get_location(location_id)

    hourly = data["hourly"]

    latitude = Decimal(str(data["latitude"]))
    longitude = Decimal(str(data["longitude"]))

    rows = []

    for time_text, temperature, wind_speed in zip(
        hourly["time"],
        hourly["temperature_2m"],
        hourly["wind_speed_10m"],
        strict=True,
    ):
        interval_start = datetime.fromisoformat(
            time_text
        ).replace(tzinfo=timezone.utc)

        rows.append(
            (
                location_id,
                interval_start,
                Decimal(str(temperature)),
                Decimal(str(wind_speed)),
                latitude,
                longitude,
                source_file.as_posix(),
            )
        )

    return rows


def insert_weather_rows(rows: list[tuple]) -> int:
    query = """
        INSERT INTO staging.weather_hourly (
            location,
            interval_start,
            temperature_c,
            wind_speed_kmh,
            latitude,
            longitude,
            source_file
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        ON CONFLICT (
            location,
            interval_start
        )
        DO UPDATE SET
            temperature_c = EXCLUDED.temperature_c,
            wind_speed_kmh = EXCLUDED.wind_speed_kmh,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            source_file = EXCLUDED.source_file,
            loaded_at = CURRENT_TIMESTAMP
        WHERE (
            staging.weather_hourly.temperature_c,
            staging.weather_hourly.wind_speed_kmh,
            staging.weather_hourly.latitude,
            staging.weather_hourly.longitude,
            staging.weather_hourly.source_file
        ) IS DISTINCT FROM (
            EXCLUDED.temperature_c,
            EXCLUDED.wind_speed_kmh,
            EXCLUDED.latitude,
            EXCLUDED.longitude,
            EXCLUDED.source_file
        )
    """

    with get_database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(query, rows)
            changed_rows = cursor.rowcount

    return changed_rows


def load_weather(
    target_date: date,
    location_id: str = DEFAULT_LOCATION,
) -> int:
    file_path = get_weather_file_path(
        target_date,
        location_id,
    )

    data = load_and_validate_weather(
        file_path=file_path,
        target_date=target_date,
    )

    rows = build_weather_rows(
        data=data,
        source_file=file_path,
        location_id=location_id,
    )

    changed_rows = insert_weather_rows(rows)

    print(
        f"Prepared {len(rows)} weather rows for "
        f"{location_id} on {target_date.isoformat()}."
    )
    print(f"Inserted or updated {changed_rows} rows.")

    return changed_rows


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load hourly weather data into PostgreSQL."
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--location",
        choices=sorted(LOCATIONS),
        default=DEFAULT_LOCATION,
        help="Weather location (default: berlin).",
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    try:
        target_date = date.fromisoformat(arguments.date)
    except ValueError as error:
        raise SystemExit(
            "Invalid date. Use the YYYY-MM-DD format."
        ) from error

    try:
        load_weather(
            target_date=target_date,
            location_id=arguments.location,
        )
    except (
        OSError,
        ValueError,
        RuntimeError,
        psycopg.Error,
    ) as error:
        raise SystemExit(
            f"Weather loading failed: {error}"
        ) from error


if __name__ == "__main__":
    main()