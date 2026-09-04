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
    run_pipeline("DE-LU", "2025-01-01")