import argparse
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from fetch_prices import fetch_prices, save_raw
from load_prices import load_prices
from validate_prices import validate_prices


def run_pipeline(zone, date_utc, refresh=False):
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

            record_count = validate_prices(data, date_utc)

        except (OSError, ValueError) as error:
            print(f"Could not reuse local file: {error}")
            print(f"Downloading data again for {date_utc}")

        else:
            print(
                f"Using validated local data for {date_utc}: "
                f"{record_count} price records"
            )
            return record_count, "reused"

    data = fetch_prices(zone, date_utc)

    output_path = save_raw(data, zone, date_utc)
    print(f"Raw data saved to: {output_path}")

    record_count = validate_prices(data, date_utc)
    print(f"Raw data validated: {record_count} price records")

    return record_count, "downloaded"


def build_analytics():
    project_dir = Path(__file__).resolve().parent

    command = [
        sys.executable,
        str(project_dir / "run_dbt.py"),
        "build",
    ]

    print("Building analytics models and running dbt tests", flush=True)

    subprocess.run(
        command,
        cwd=project_dir,
        check=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Download and load electricity prices, "
            "then build and test daily analytics."
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
        help="Download data again even when a valid local file exists",
    )

    args = parser.parse_args()

    if args.start > args.end:
        parser.error("--start must be on or before --end")

    current_date = args.start
    total_records = 0
    total_changed = 0
    day_counts = {"downloaded": 0, "reused": 0}

    while current_date <= args.end:
        date_utc = current_date.isoformat()
        print(f"Processing date: {date_utc}")

        record_count, status = run_pipeline(
            "DE-LU",
            date_utc,
            refresh=args.refresh,
        )

        changed_count = load_prices(date_utc)

        total_records += record_count
        total_changed += changed_count
        day_counts[status] += 1

        current_date += timedelta(days=1)

    print(f"Date range checked: {total_records} price records")
    print(f"Days downloaded: {day_counts['downloaded']}")
    print(f"Days reused: {day_counts['reused']}")
    print(f"Database records inserted or updated: {total_changed}")

    build_analytics()

    print("Pipeline completed successfully")