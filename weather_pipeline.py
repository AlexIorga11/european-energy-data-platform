import argparse
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import psycopg

from fetch_weather_batches import fetch_batches
from load_weather import load_weather
from locations import DEFAULT_LOCATION, LOCATIONS


PROJECT_DIR = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Load weather and rebuild analytics.")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--location", choices=sorted(LOCATIONS), default=DEFAULT_LOCATION)
    parser.add_argument("--batch-days", type=int, choices=range(1, 31), default=7)
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("--start must be on or before --end")

    os.chdir(PROJECT_DIR)
    changes = 0
    start = args.start
    try:
        while start <= args.end:
            end = min(start + timedelta(days=args.batch_days - 1), args.end)
            fetch_batches(args.location, start, end, args.batch_days)
            day = start
            while day <= end:
                changes += load_weather(day, location_id=args.location)
                day += timedelta(days=1)
            start = end + timedelta(days=1)

        subprocess.run(
            [sys.executable, str(PROJECT_DIR / "run_dbt.py"), "build"],
            cwd=PROJECT_DIR,
            check=True,
        )
    except (OSError, ValueError, RuntimeError, psycopg.Error,
            subprocess.CalledProcessError) as error:
        print(f"Weather pipeline stopped: {error}", flush=True)
        print("Saved files and committed rows remain available for retry.", flush=True)
        return 1

    print(f"Weather records inserted or updated: {changes}", flush=True)
    print("Weather pipeline completed successfully", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())