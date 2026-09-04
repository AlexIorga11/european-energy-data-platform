import argparse
import json
import time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://archive-api.open-meteo.com/v1/archive"

LOCATION_NAME = "berlin"
LATITUDE = 52.52
LONGITUDE = 13.41

MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 30


def build_url(target_date: date) -> str:
    parameters = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": target_date.isoformat(),
        "end_date": target_date.isoformat(),
        "hourly": "temperature_2m,wind_speed_10m",
        "timezone": "UTC",
    }

    return f"{API_URL}?{urlencode(parameters)}"


def get_output_path(target_date: date) -> Path:
    return (
        Path("data")
        / "raw"
        / "open_meteo"
        / f"location={LOCATION_NAME}"
        / f"{target_date.isoformat()}.json"
    )


def download_weather_data(target_date: date) -> dict:
    url = build_url(target_date)

    request = Request(
        url,
        headers={
            "User-Agent": "european-energy-data-platform/1.0"
        },
    )

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urlopen(
                request,
                timeout=REQUEST_TIMEOUT_SECONDS,
            ) as response:
                return json.load(response)

        except HTTPError as error:
            retryable = error.code == 429 or 500 <= error.code < 600

            if not retryable or attempt == MAX_ATTEMPTS:
                raise RuntimeError(
                    f"Weather API returned HTTP {error.code}"
                ) from error

            retry_after = error.headers.get("Retry-After")
            wait_seconds = int(retry_after) if retry_after else attempt * 2

            print(
                f"Request failed with HTTP {error.code}. "
                f"Retrying in {wait_seconds} seconds."
            )
            time.sleep(wait_seconds)

        except URLError as error:
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(
                    f"Could not connect to the weather API: {error.reason}"
                ) from error

            wait_seconds = attempt * 2

            print(
                "Connection failed. "
                f"Retrying in {wait_seconds} seconds."
            )
            time.sleep(wait_seconds)

    raise RuntimeError("Weather data could not be downloaded")


def save_weather_data(data: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = output_path.with_suffix(".json.tmp")

    with temporary_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(data, file, indent=2)

    temporary_path.replace(output_path)


def fetch_weather(
    target_date: date,
    refresh: bool = False,
) -> Path:
    output_path = get_output_path(target_date)

    if output_path.exists() and not refresh:
        print(f"Using cached weather file: {output_path}")
        return output_path

    print(
        f"Downloading weather data for {LOCATION_NAME} "
        f"on {target_date.isoformat()}."
    )

    data = download_weather_data(target_date)
    save_weather_data(data, output_path)

    print(f"Weather data saved to: {output_path}")

    return output_path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download hourly historical weather data."
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Download the file again even if it already exists.",
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

    fetch_weather(
        target_date=target_date,
        refresh=arguments.refresh,
    )


if __name__ == "__main__":
    main()