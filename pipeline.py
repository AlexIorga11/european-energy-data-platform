import argparse
from datetime import date

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
        description="Download, save and validate daily electricity prices."
    )

    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        required=True,
        help="UTC date to process, for example 2025-01-02",
    )

    args = parser.parse_args()

    run_pipeline("DE-LU", args.date.isoformat())