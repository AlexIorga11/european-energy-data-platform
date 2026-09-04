import argparse
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from database import get_connection
from validate_prices import validate_prices


def load_prices(date_utc):
    zone = "DE-LU"
    project_dir = Path(__file__).resolve().parent

    input_path = (
        project_dir
        / "data"
        / "raw"
        / "energy_charts"
        / f"zone={zone}"
        / f"{date_utc}.json"
    )

    with input_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    record_count = validate_prices(data, date_utc)
    source_file = input_path.relative_to(project_dir).as_posix()

    rows = []

    for timestamp, price in zip(data["unix_seconds"], data["price"]):
        interval_start = datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        )

        rows.append(
            (
                zone,
                interval_start,
                Decimal(str(price)),
                source_file,
            )
        )

    query = """
        INSERT INTO staging.energy_prices (
            zone,
            interval_start,
            price_eur_per_mwh,
            source_file
        )
        VALUES (%s, %s, %s, %s)

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

    print(f"Validated records: {record_count}")
    print(f"Inserted or updated records: {changed_count}")
    print(f"Load completed for {date_utc}")

    return changed_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load a local electricity price file into PostgreSQL."
    )

    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        required=True,
        help="UTC date to load, in YYYY-MM-DD format",
    )

    args = parser.parse_args()
    load_prices(args.date.isoformat())