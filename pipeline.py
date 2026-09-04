import argparse
from datetime import date, timedelta

from fetch_prices import fetch_prices, save_raw
from validate_prices import validate_prices


def run_pipeline(zone, date_utc):
    data = fetch_prices(zone, date_utc)

    output_path = save_raw(data, zone, date_utc)
    print(f"Raw data saved to: {output_path}")

    record_count = validate_prices(data, date_utc)
    print(f"Pipeline completed: {record_count} price records")

    return record_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download, save and validate electricity prices by date range."
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

    args = parser.parse_args()

    if args.start > args.end:
        parser.error("--start must be on or before --end")

    current_date = args.start
    total_records = 0

    while current_date <= args.end:
        date_utc = current_date.isoformat()
        print(f"Processing date: {date_utc}")

        record_count = run_pipeline("DE-LU", date_utc)
        total_records += record_count

        current_date += timedelta(days=1)

    print(f"Date range completed: {total_records} price records")