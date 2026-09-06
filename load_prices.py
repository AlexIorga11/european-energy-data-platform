import argparse
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from database import get_connection
from price_rules import PRICE_ZONES, price_interval
from validate_prices import validate_prices


PROJECT_DIR = Path(__file__).resolve().parent


def load_prices(date_utc, expected_interval_seconds=None, zone="DE-LU"):
    day = date.fromisoformat(date_utc)
    if zone not in PRICE_ZONES:
        raise ValueError(f"Price zone is not configured: {zone}")
    if expected_interval_seconds is None:
        expected_interval_seconds = price_interval(zone, day, day) * 60
    input_path = (
        PROJECT_DIR / "data" / "raw" / "energy_charts"
        / f"zone={zone}" / f"{date_utc}.json"
    )
    with input_path.open(encoding="utf-8") as source:
        data = json.load(source)
    record_count = validate_prices(
        data, date_utc, expected_interval_seconds=expected_interval_seconds,
    )
    source_file = input_path.relative_to(PROJECT_DIR).as_posix()
    rows = [
        (zone, datetime.fromtimestamp(timestamp, tz=timezone.utc),
         Decimal(str(price)), source_file)
        for timestamp, price in zip(data["unix_seconds"], data["price"], strict=True)
    ]
    query = """
        INSERT INTO staging.energy_prices (
            zone, interval_start, price_eur_per_mwh, source_file
        ) VALUES (%s, %s, %s, %s)
        ON CONFLICT (zone, interval_start)
        DO UPDATE SET
            price_eur_per_mwh = EXCLUDED.price_eur_per_mwh,
            source_file = EXCLUDED.source_file,
            loaded_at = CURRENT_TIMESTAMP
        WHERE staging.energy_prices.price_eur_per_mwh
            IS DISTINCT FROM EXCLUDED.price_eur_per_mwh
           OR staging.energy_prices.source_file
            IS DISTINCT FROM EXCLUDED.source_file
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(query, rows)
            changed_count = cursor.rowcount
    print(f"Validated records ({zone}, {date_utc}): {record_count}", flush=True)
    print(f"Price records inserted or updated: {changed_count}", flush=True)
    return changed_count


def main():
    parser = argparse.ArgumentParser(description="Load validated daily prices into PostgreSQL.")
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--zone", choices=PRICE_ZONES, default="DE-LU")
    parser.add_argument("--interval-minutes", type=int, choices=[15, 30, 60])
    args = parser.parse_args()
    interval = args.interval_minutes or price_interval(args.zone, args.date, args.date)
    load_prices(args.date.isoformat(), interval * 60, zone=args.zone)


if __name__ == "__main__":
    main()
