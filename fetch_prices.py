import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen


def get_retry_delay(retry_after, attempt):
    fallback_delay = 30 * (2 ** (attempt - 1))

    if retry_after is None:
        return fallback_delay

    try:
        server_delay = int(retry_after)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(retry_after)

            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)

            server_delay = (
                retry_at - datetime.now(timezone.utc)
            ).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return fallback_delay

    return max(fallback_delay, server_delay)


def fetch_prices(zone, date_utc):
    base_url = "https://api.energy-charts.info/price"

    params = {
        "bzn": zone,
        "start": f"{date_utc}T00:00Z",
        "end": f"{date_utc}T23:59Z",
    }

    url = f"{base_url}?{urlencode(params)}"
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            with urlopen(url, timeout=30) as response:
                print("HTTP status:", response.status)
                return json.load(response)

        except HTTPError as error:
            if error.code != 429 or attempt == max_attempts:
                raise

            delay = get_retry_delay(
                error.headers.get("Retry-After"),
                attempt,
            )
            error.close()

            print(
                f"Rate limited on attempt {attempt}/{max_attempts}. "
                f"Retrying in {delay:.0f} seconds."
            )
            time.sleep(delay)


def save_raw(data, zone, date_utc):
    project_dir = Path(__file__).resolve().parent
    output_dir = (
        project_dir
        / "data"
        / "raw"
        / "energy_charts"
        / f"zone={zone}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{date_utc}.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    return output_path


if __name__ == "__main__":
    zone = "DE-LU"
    date_utc = "2025-01-01"

    data = fetch_prices(zone, date_utc)
    output_path = save_raw(data, zone, date_utc)

    print(f"Saved data to: {output_path}")