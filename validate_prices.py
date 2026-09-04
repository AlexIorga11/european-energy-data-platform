import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path


def validate_prices(data, date_utc, expected_interval_seconds=3600):
    if (
        type(expected_interval_seconds) is not int
        or expected_interval_seconds <= 0
        or 86400 % expected_interval_seconds != 0
    ):
        raise ValueError(
            "Expected interval must be a positive integer "
            "that divides a UTC day exactly"
        )

    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")

    if data.get("unit") != "EUR / MWh":
        raise ValueError(f"Unexpected price unit: {data.get('unit')}")

    timestamps = data.get("unix_seconds")
    prices = data.get("price")

    if not isinstance(timestamps, list) or not isinstance(prices, list):
        raise ValueError("Timestamps and prices must be lists")

    if not timestamps or not prices:
        raise ValueError("The dataset is empty")

    if len(timestamps) != len(prices):
        raise ValueError("Timestamp and price counts do not match")

    for timestamp in timestamps:
        if type(timestamp) is not int:
            raise ValueError(f"Invalid timestamp: {timestamp}")

    if len(set(timestamps)) != len(timestamps):
        raise ValueError("Duplicate timestamps found")

    if timestamps != sorted(timestamps):
        raise ValueError("Timestamps are not in chronological order")

    day_start = datetime.strptime(date_utc, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    day_end = day_start + timedelta(days=1)

    start_timestamp = int(day_start.timestamp())
    end_timestamp = int(day_end.timestamp())

    for timestamp in timestamps:
        if not start_timestamp <= timestamp < end_timestamp:
            raise ValueError(
                f"Timestamp outside the requested UTC day: {timestamp}"
            )

    for price in prices:
        if type(price) not in (int, float) or not math.isfinite(price):
            raise ValueError(f"Invalid price: {price}")

    expected_timestamps = set(
        range(
            start_timestamp,
            end_timestamp,
            expected_interval_seconds,
        )
    )
    actual_timestamps = set(timestamps)

    missing = expected_timestamps - actual_timestamps
    unexpected = actual_timestamps - expected_timestamps

    if missing or unexpected:
        raise ValueError(
            "Incomplete or misaligned UTC day: "
            f"{len(missing)} missing intervals, "
            f"{len(unexpected)} unexpected timestamps "
            f"for a {expected_interval_seconds}-second resolution"
        )

    return len(prices)


if __name__ == "__main__":
    zone = "DE-LU"
    date_utc = "2025-01-01"

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
    first_interval = datetime.fromtimestamp(
        data["unix_seconds"][0], tz=timezone.utc
    )

    print(f"Validation passed: {record_count} price records")
    print(f"First interval starts at: {first_interval.isoformat()}")