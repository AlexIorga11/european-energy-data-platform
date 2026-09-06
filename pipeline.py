import argparse
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import psycopg

import fetch_price_batches as price_batches
import fetch_weather_batches as weather_batches
from load_prices import load_prices
from load_weather import load_weather
from locations import DEFAULT_LOCATION, LOCATIONS, get_location
from price_rules import price_interval


PROJECT_DIR = Path(__file__).resolve().parent


def iter_batches(start, end, batch_days):
    days = []
    current = start
    while current <= end:
        days.append(current)
        if len(days) == batch_days:
            yield days
            days = []
        current += timedelta(days=1)
    if days:
        yield days


def prepare_prices(zone, days, interval_minutes, refresh):
    if not refresh:
        price_batches.fetch_batches(
            zone=zone,
            start=days[0],
            end=days[-1],
            batch_days=len(days),
            interval_minutes=interval_minutes,
        )
        return

    data = price_batches.download_range(zone, days[0], days[-1])
    daily = price_batches.split_and_validate(data, days, interval_minutes * 60)
    for day, payload in daily.items():
        price_batches.save_raw(payload, zone, day.isoformat())
    print(f"Refreshed price files: {len(days)} days", flush=True)


def prepare_weather(location_id, days, refresh):
    if not refresh:
        weather_batches.fetch_batches(
            location_id=location_id,
            start=days[0],
            end=days[-1],
            batch_days=len(days),
        )
        return

    data = weather_batches.download_range(location_id, days[0], days[-1])
    daily = weather_batches.split_and_validate(data, days)
    for day, payload in daily.items():
        weather_batches.save_daily(payload, location_id, day)
    print(f"Refreshed weather files: {location_id}, {len(days)} days", flush=True)


def build_analytics():
    print("Building analytics models and running dbt tests", flush=True)
    subprocess.run(
        [sys.executable, str(PROJECT_DIR / "run_dbt.py"), "build"],
        cwd=PROJECT_DIR,
        check=True,
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Download data in batches, load PostgreSQL and run dbt."
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--locations", nargs="+", choices=sorted(LOCATIONS),
        default=[DEFAULT_LOCATION],
    )
    parser.add_argument(
        "--batch-days", type=int, choices=range(1, 31), default=7,
        help="Maximum days per download batch (default: 7)",
    )
    parser.add_argument(
        "--interval-minutes", type=int, choices=[15, 30, 60],
        help="Override the automatic price interval for all selected zones",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Download again even when valid local files exist",
    )
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("--start must be on or before --end")

    args.locations = list(dict.fromkeys(args.locations))
    zones = sorted({
        get_location(location_id)["energy_zone"]
        for location_id in args.locations
        if get_location(location_id)["energy_zone"] is not None
    })
    try:
        args.zone_intervals = {
            zone: args.interval_minutes or price_interval(zone, args.start, args.end)
            for zone in zones
        }
    except ValueError as error:
        parser.error(str(error))
    return args


def main():
    args = parse_arguments()
    os.chdir(PROJECT_DIR)
    price_changes = {zone: 0 for zone in args.zone_intervals}
    weather_changes = {location_id: 0 for location_id in args.locations}
    completed_days = 0

    print(f"Period: {args.start} to {args.end}", flush=True)
    print(f"Weather locations: {', '.join(args.locations)}", flush=True)
    print(f"Maximum batch size: {args.batch_days} days", flush=True)
    for zone, interval in args.zone_intervals.items():
        print(f"Price zone: {zone}, expected interval: {interval} minutes", flush=True)

    try:
        for days in iter_batches(args.start, args.end, args.batch_days):
            print(f"\nProcessing batch: {days[0]} to {days[-1]}", flush=True)
            for zone, interval in args.zone_intervals.items():
                prepare_prices(zone, days, interval, args.refresh)
            for location_id in args.locations:
                prepare_weather(location_id, days, args.refresh)

            for day in days:
                print(f"Loading PostgreSQL: {day}", flush=True)
                for zone, interval in args.zone_intervals.items():
                    price_changes[zone] += load_prices(
                        day.isoformat(),
                        expected_interval_seconds=interval * 60,
                        zone=zone,
                    )
                for location_id in args.locations:
                    weather_changes[location_id] += load_weather(
                        day, location_id=location_id,
                    )
                completed_days += 1

        build_analytics()
    except (
        OSError, ValueError, RuntimeError,
        psycopg.Error, subprocess.CalledProcessError,
    ) as error:
        print(f"Pipeline stopped: {error}", flush=True)
        print(
            "Saved files and committed database rows remain available. "
            "Rerun the same command to resume. Analytics may be outdated.",
            flush=True,
        )
        return 1

    print("\nPipeline summary")
    print(f"Days processed: {completed_days}")
    for zone, changes in price_changes.items():
        print(f"Price records inserted or updated ({zone}): {changes}")
    for location_id, changes in weather_changes.items():
        print(f"Weather records inserted or updated ({location_id}): {changes}")
    print("Pipeline completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
