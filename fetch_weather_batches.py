import argparse
import json
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from fetch_prices import get_retry_delay
from locations import DEFAULT_LOCATION, LOCATIONS, get_location
from validate_weather import validate_weather


PROJECT_DIR = Path(__file__).resolve().parent
HOURLY_FIELDS = ("time", "temperature_2m", "wind_speed_10m")


def daily_path(location_id, day):
    get_location(location_id)
    return (
        PROJECT_DIR / "data" / "raw" / "open_meteo"
        / f"location={location_id}" / f"{day.isoformat()}.json"
    )


def has_valid_file(location_id, day):
    try:
        path = daily_path(location_id, day)
        data = json.loads(path.read_text(encoding="utf-8"))
        validate_weather(data, day)
    except (OSError, ValueError):
        return False
    return True


def missing_batches(location_id, start, end, batch_days):
    batch = []
    day = start
    while day <= end:
        if has_valid_file(location_id, day):
            if batch:
                yield batch
                batch = []
            print(f"Reusing validated file: {location_id}, {day}", flush=True)
        else:
            batch.append(day)
            if len(batch) == batch_days:
                yield batch
                batch = []
        day += timedelta(days=1)
    if batch:
        yield batch


def download_range(location_id, start, end):
    location = get_location(location_id)
    params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": "temperature_2m,wind_speed_10m",
        "timezone": "UTC",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
    }
    url = "https://archive-api.open-meteo.com/v1/archive?" + urlencode(params)
    for attempt in range(1, 4):
        print(
            f"Request {location_id}: {start} to {end}, attempt {attempt}/3",
            flush=True,
        )
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


def split_and_validate(data, days):
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    hourly = data.get("hourly")
    if not isinstance(hourly, dict):
        raise ValueError("Missing hourly weather data")
    for field in HOURLY_FIELDS:
        if not isinstance(hourly.get(field), list):
            raise ValueError(f"Missing or invalid hourly field: {field}")
    if len({len(hourly[field]) for field in HOURLY_FIELDS}) != 1:
        raise ValueError("Hourly arrays must have equal lengths")

    daily = {
        day: {**data, "hourly": {field: [] for field in HOURLY_FIELDS}}
        for day in days
    }
    for index, timestamp in enumerate(hourly["time"]):
        if not isinstance(timestamp, str):
            raise ValueError(f"Invalid weather timestamp: {timestamp}")
        day = date.fromisoformat(timestamp[:10])
        if day not in daily:
            raise ValueError(f"Date outside the requested range: {day}")
        for field in HOURLY_FIELDS:
            daily[day]["hourly"][field].append(hourly[field][index])

    for day, payload in daily.items():
        validate_weather(payload, day)
    return daily


def save_daily(payload, location_id, day):
    path = daily_path(location_id, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    temporary_path.replace(path)
    return path


def fetch_batches(location_id, start, end, batch_days=7):
    get_location(location_id)
    if start > end:
        raise ValueError("Start date must be on or before end date")
    if not 1 <= batch_days <= 30:
        raise ValueError("Batch size must be between 1 and 30 days")

    downloaded = 0
    batches = 0
    for days in missing_batches(location_id, start, end, batch_days):
        data = download_range(location_id, days[0], days[-1])
        daily = split_and_validate(data, days)
        for day, payload in daily.items():
            path = save_daily(payload, location_id, day)
            print(f"Saved 24 validated weather hours: {path}", flush=True)
            downloaded += 1
        batches += 1

    total = (end - start).days + 1
    print(f"Weather location: {location_id}")
    print(f"Completed batches: {batches}")
    print(f"Days downloaded: {downloaded}")
    print(f"Days reused: {total - downloaded}")


def main():
    parser = argparse.ArgumentParser(
        description="Download weather batches and save validated daily files."
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--location", choices=sorted(LOCATIONS), default=DEFAULT_LOCATION)
    parser.add_argument("--batch-days", type=int, choices=range(1, 31), default=7)
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("--start must be on or before --end")
    try:
        fetch_batches(args.location, args.start, args.end, args.batch_days)
    except (OSError, ValueError) as error:
        print(f"Download stopped: {error}")
        print("Previously saved days remain available. Rerun to resume.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())