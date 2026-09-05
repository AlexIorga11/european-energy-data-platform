import argparse
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from fetch_prices import fetch_prices, save_raw
from fetch_weather import fetch_weather
from load_prices import load_prices
from load_weather import load_weather
from validate_prices import validate_prices
from validate_weather import (
    get_weather_file_path,
    load_and_validate_weather,
)


def run_price_pipeline(
    zone,
    date_utc,
    refresh=False,
    expected_interval_seconds=3600,
):
    project_dir = Path(__file__).resolve().parent
    input_path = (
        project_dir
        / "data"
        / "raw"
        / "energy_charts"
        / f"zone={zone}"
        / f"{date_utc}.json"
    )

    if input_path.exists() and not refresh:
        try:
            with input_path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            record_count = validate_prices(
                data,
                date_utc,
                expected_interval_seconds=expected_interval_seconds,
            )

        except (OSError, ValueError) as error:
            print(f"Could not reuse local price file: {error}")
            print(f"Downloading price data again for {date_utc}")

        else:
            print(
                f"Using validated local price data for {date_utc}: "
                f"{record_count} records"
            )
            return record_count, "reused"

    data = fetch_prices(zone, date_utc)

    output_path = save_raw(data, zone, date_utc)
    print(f"Raw price data saved to: {output_path}")

    record_count = validate_prices(
        data,
        date_utc,
        expected_interval_seconds=expected_interval_seconds,
    )
    print(f"Raw price data validated: {record_count} records")

    return record_count, "downloaded"


def run_weather_pipeline(
    target_date,
    refresh=False,
):
    input_path = get_weather_file_path(target_date)

    if input_path.exists() and not refresh:
        try:
            data = load_and_validate_weather(
                file_path=input_path,
                target_date=target_date,
            )

        except (
            OSError,
            json.JSONDecodeError,
            ValueError,
        ) as error:
            print(f"Could not reuse local weather file: {error}")
            print(
                "Downloading weather data again for "
                f"{target_date.isoformat()}"
            )

        else:
            record_count = len(data["hourly"]["time"])

            print(
                "Using validated local weather data for "
                f"{target_date.isoformat()}: "
                f"{record_count} records"
            )

            return record_count, "reused"

    output_path = fetch_weather(
        target_date=target_date,
        refresh=True,
    )

    data = load_and_validate_weather(
        file_path=output_path,
        target_date=target_date,
    )

    record_count = len(data["hourly"]["time"])

    print(
        f"Raw weather data validated: "
        f"{record_count} records"
    )

    return record_count, "downloaded"


def build_analytics():
    project_dir = Path(__file__).resolve().parent

    command = [
        sys.executable,
        str(project_dir / "run_dbt.py"),
        "build",
    ]

    print(
        "Building analytics models and running dbt tests",
        flush=True,
    )

    subprocess.run(
        command,
        cwd=project_dir,
        check=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Download and load electricity prices and weather data, "
            "then build and test analytics models."
        )
    )

    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        required=True,
        help="First UTC date to process, inclusive",
    )

    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        required=True,
        help="Last UTC date to process, inclusive",
    )

    parser.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "Download data again even when valid local files exist"
        ),
    )

    parser.add_argument(
        "--interval-minutes",
        type=int,
        choices=[15, 60],
        default=60,
        help="Expected price interval in minutes (default: 60)",
    )

    args = parser.parse_args()

    if args.start > args.end:
        parser.error("--start must be on or before --end")

    expected_interval_seconds = args.interval_minutes * 60

    print(f"Expected price interval: {args.interval_minutes} minutes")

    current_date = args.start

    total_price_records = 0
    total_weather_records = 0

    total_price_changes = 0
    total_weather_changes = 0

    price_day_counts = {
        "downloaded": 0,
        "reused": 0,
    }

    weather_day_counts = {
        "downloaded": 0,
        "reused": 0,
    }

    while current_date <= args.end:
        date_utc = current_date.isoformat()

        print()
        print(f"Processing date: {date_utc}")

        price_record_count, price_status = run_price_pipeline(
            zone="DE-LU",
            date_utc=date_utc,
            refresh=args.refresh,
            expected_interval_seconds=expected_interval_seconds,
        )

        price_changed_count = load_prices(
            date_utc,
            expected_interval_seconds=expected_interval_seconds,
        )

        weather_record_count, weather_status = (
            run_weather_pipeline(
                target_date=current_date,
                refresh=args.refresh,
            )
        )

        weather_changed_count = load_weather(current_date)

        total_price_records += price_record_count
        total_weather_records += weather_record_count

        total_price_changes += price_changed_count
        total_weather_changes += weather_changed_count

        price_day_counts[price_status] += 1
        weather_day_counts[weather_status] += 1

        current_date += timedelta(days=1)

    print()
    print("Pipeline summary")
    print(
        f"Price records checked: {total_price_records}"
    )
    print(
        f"Weather records checked: {total_weather_records}"
    )
    print(
        f"Price days downloaded: "
        f"{price_day_counts['downloaded']}"
    )
    print(
        f"Price days reused: "
        f"{price_day_counts['reused']}"
    )
    print(
        f"Weather days downloaded: "
        f"{weather_day_counts['downloaded']}"
    )
    print(
        f"Weather days reused: "
        f"{weather_day_counts['reused']}"
    )
    print(
        "Price records inserted or updated: "
        f"{total_price_changes}"
    )
    print(
        "Weather records inserted or updated: "
        f"{total_weather_changes}"
    )

    build_analytics()

    print("Pipeline completed successfully")