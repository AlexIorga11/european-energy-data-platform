import argparse
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from fetch_prices import get_retry_delay, save_raw
from validate_prices import validate_prices
from price_rules import PRICE_ZONES, price_interval


PROJECT_DIR = Path(__file__).resolve().parent


def daily_path(zone, day):
    return (
        PROJECT_DIR / "data" / "raw" / "energy_charts"
        / f"zone={zone}" / f"{day.isoformat()}.json"
    )


def has_valid_file(zone, day, interval_seconds):
    try:
        data = json.loads(daily_path(zone, day).read_text(encoding="utf-8"))
        validate_prices(data, day.isoformat(), interval_seconds)
    except (OSError, ValueError):
        return False
    return True


def missing_batches(zone, start, end, batch_days, interval_seconds):
    batch = []
    day = start
    while day <= end:
        if has_valid_file(zone, day, interval_seconds):
            if batch:
                yield batch
                batch = []
            print(f"Reusing validated file: {day}", flush=True)
        else:
            batch.append(day)
            if len(batch) == batch_days:
                yield batch
                batch = []
        day += timedelta(days=1)
    if batch:
        yield batch


def download_range(zone, start, end):
    params = {
        "bzn": zone,
        "start": f"{start.isoformat()}T00:00Z",
        "end": f"{end.isoformat()}T23:59Z",
    }
    url = "https://api.energy-charts.info/price?" + urlencode(params)
    for attempt in range(1, 4):
        print(f"Request {zone}: {start} to {end}, attempt {attempt}/3", flush=True)
        try:
            with urlopen(url, timeout=60) as response:
                return json.load(response)
        except HTTPError as error:
            code = error.code
            retry_after = error.headers.get("Retry-After")
            error.close()
            if code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
            delay = get_retry_delay(retry_after, attempt)
        except (URLError, TimeoutError):
            if attempt == 3:
                raise
            delay = get_retry_delay(None, attempt)
        print(f"Temporary request failure. Waiting {delay:.0f}s.", flush=True)
        time.sleep(delay)


def split_and_validate(data, days, interval_seconds):
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    timestamps = data.get("unix_seconds")
    prices = data.get("price")
    if not isinstance(timestamps, list) or not isinstance(prices, list):
        raise ValueError("Timestamps and prices must be lists")
    if len(timestamps) != len(prices):
        raise ValueError("Timestamp and price counts do not match")

    daily = {
        day: {**data, "unix_seconds": [], "price": []}
        for day in days
    }
    lower = int(datetime.combine(
        days[0], datetime.min.time(), timezone.utc
    ).timestamp())
    upper = int(datetime.combine(
        days[-1] + timedelta(days=1), datetime.min.time(), timezone.utc
    ).timestamp())

    for timestamp, price in zip(timestamps, prices, strict=True):
        if type(timestamp) is not int or not lower <= timestamp < upper:
            raise ValueError(f"Invalid or out-of-range timestamp: {timestamp}")
        day = datetime.fromtimestamp(timestamp, timezone.utc).date()
        if day not in daily:
            raise ValueError(f"Unexpected date in response: {day}")
        daily[day]["unix_seconds"].append(timestamp)
        daily[day]["price"].append(price)

    for day, payload in daily.items():
        validate_prices(payload, day.isoformat(), interval_seconds)
    return daily


def fetch_batches(zone, start, end, batch_days=7, interval_minutes=None):
    if zone not in PRICE_ZONES:
        raise ValueError(f"Price zone is not configured: {zone}")
    if start > end:
        raise ValueError("Start date must be on or before end date")
    if not 1 <= batch_days <= 30:
        raise ValueError("Batch size must be between 1 and 30 days")
    if interval_minutes is None:
        interval_minutes = price_interval(zone, start, end)
    if interval_minutes not in (15, 30, 60):
        raise ValueError("Interval must be 15, 30 or 60 minutes")

    interval_seconds = interval_minutes * 60
    downloaded = 0
    batches = 0
    for days in missing_batches(zone, start, end, batch_days, interval_seconds):
        data = download_range(zone, days[0], days[-1])
        daily = split_and_validate(data, days, interval_seconds)
        for day, payload in daily.items():
            path = save_raw(payload, zone, day.isoformat())
            print(f"Saved {len(payload['price'])} validated records: {path}", flush=True)
            downloaded += 1
        batches += 1

    total = (end - start).days + 1
    print(f"Completed batches: {batches}")
    print(f"Days downloaded: {downloaded}")
    print(f"Days reused: {total - downloaded}")


def main():
    parser = argparse.ArgumentParser(
        description="Download price batches and save validated daily files."
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--zone", choices=PRICE_ZONES, default="DE-LU")
    parser.add_argument("--batch-days", type=int, choices=range(1, 31), default=7)
    parser.add_argument("--interval-minutes", type=int, choices=[15, 30, 60])
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("--start must be on or before --end")
    try:
        fetch_batches(
            args.zone, args.start, args.end,
            args.batch_days, args.interval_minutes,
        )
    except (OSError, ValueError) as error:
        print(f"Download stopped: {error}")
        print("Previously saved days remain available. Rerun to resume.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
