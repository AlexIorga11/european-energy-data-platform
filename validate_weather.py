import argparse
import json
import math
from datetime import date, datetime, time, timedelta
from pathlib import Path


LOCATION_NAME = "berlin"


def get_weather_file_path(target_date: date) -> Path:
    return (
        Path("data")
        / "raw"
        / "open_meteo"
        / f"location={LOCATION_NAME}"
        / f"{target_date.isoformat()}.json"
    )


def is_valid_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def build_expected_times(target_date: date) -> list[str]:
    start = datetime.combine(target_date, time.min)

    return [
        (start + timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M")
        for hour in range(24)
    ]


def validate_weather(
    data: object,
    target_date: date,
) -> None:
    if not isinstance(data, dict):
        raise ValueError("Weather response must be a JSON object")

    if data.get("utc_offset_seconds") != 0:
        raise ValueError("Weather data must use the UTC timezone")

    hourly = data.get("hourly")

    if not isinstance(hourly, dict):
        raise ValueError("Missing or invalid hourly data")

    hourly_units = data.get("hourly_units")

    if not isinstance(hourly_units, dict):
        raise ValueError("Missing or invalid hourly units")

    if hourly_units.get("temperature_2m") != "°C":
        raise ValueError("Temperature unit must be °C")

    if hourly_units.get("wind_speed_10m") != "km/h":
        raise ValueError("Wind speed unit must be km/h")

    times = hourly.get("time")
    temperatures = hourly.get("temperature_2m")
    wind_speeds = hourly.get("wind_speed_10m")

    if not isinstance(times, list):
        raise ValueError("Hourly times must be a list")

    if not isinstance(temperatures, list):
        raise ValueError("Hourly temperatures must be a list")

    if not isinstance(wind_speeds, list):
        raise ValueError("Hourly wind speeds must be a list")

    if not times:
        raise ValueError("Hourly weather data cannot be empty")

    if not (
        len(times)
        == len(temperatures)
        == len(wind_speeds)
    ):
        raise ValueError(
            "Times, temperatures and wind speeds must have equal lengths"
        )

    expected_times = build_expected_times(target_date)

    if times != expected_times:
        raise ValueError(
            "Weather data must contain all 24 UTC hours in order"
        )

    for index, temperature in enumerate(temperatures):
        if not is_valid_number(temperature):
            raise ValueError(
                f"Invalid temperature at position {index}"
            )

    for index, wind_speed in enumerate(wind_speeds):
        if not is_valid_number(wind_speed):
            raise ValueError(
                f"Invalid wind speed at position {index}"
            )

        if wind_speed < 0:
            raise ValueError(
                f"Wind speed cannot be negative at position {index}"
            )


def load_and_validate_weather(
    file_path: Path,
    target_date: date,
) -> dict:
    if not file_path.exists():
        raise FileNotFoundError(
            f"Weather file does not exist: {file_path}"
        )

    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    validate_weather(
        data=data,
        target_date=target_date,
    )

    return data


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate an hourly weather JSON file."
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Date in YYYY-MM-DD format.",
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

    file_path = get_weather_file_path(target_date)

    try:
        load_and_validate_weather(
            file_path=file_path,
            target_date=target_date,
        )
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        raise SystemExit(
            f"Weather validation failed: {error}"
        ) from error

    print(f"Weather file is valid: {file_path}")


if __name__ == "__main__":
    main()