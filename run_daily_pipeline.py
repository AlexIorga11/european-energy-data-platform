import argparse
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from locations import DEFAULT_LOCATION, LOCATIONS


PROJECT_DIR = Path(__file__).resolve().parent
LOG_DIR = PROJECT_DIR / "logs"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the pipeline for a recent date window."
    )

    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        help="Optional last UTC date, inclusive.",
    )

    parser.add_argument(
        "--lag-days",
        type=int,
        default=7,
        help="Days behind the current UTC date (default: 7).",
    )

    parser.add_argument(
        "--lookback-days",
        type=int,
        default=3,
        help="Number of days to process (default: 3).",
    )

    parser.add_argument(
        "--locations",
        nargs="+",
        choices=sorted(LOCATIONS),
        default=[DEFAULT_LOCATION],
        help="Weather locations to process (default: berlin).",
    )

    parser.add_argument(
        "--interval-minutes",
        type=int,
        choices=[15, 60],
        default=15,
        help="Expected price interval in minutes (default: 15).",
    )

    arguments = parser.parse_args()

    if arguments.lag_days < 1:
        parser.error("--lag-days must be at least 1")

    if arguments.lookback_days < 1:
        parser.error("--lookback-days must be at least 1")

    arguments.locations = list(dict.fromkeys(arguments.locations))

    return arguments


def main() -> int:
    arguments = parse_arguments()

    now = datetime.now(timezone.utc)

    end_date = arguments.end or (
        now.date() - timedelta(days=arguments.lag_days)
    )

    start_date = end_date - timedelta(
        days=arguments.lookback_days - 1
    )

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_path = LOG_DIR / (
        f"daily_pipeline_{now.strftime('%Y%m%dT%H%M%S%fZ')}.log"
    )

    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUNBUFFERED"] = "1"

    commands = [
        [
            "docker",
            "compose",
            "up",
            "-d",
            "--wait",
            "--wait-timeout",
            "120",
        ],
        [
            sys.executable,
            str(PROJECT_DIR / "pipeline.py"),
            "--start",
            start_date.isoformat(),
            "--end",
            end_date.isoformat(),
            "--locations",
            *arguments.locations,
            "--interval-minutes",
            str(arguments.interval_minutes),
        ],
    ]

    print(
        f"Processing {start_date.isoformat()} "
        f"through {end_date.isoformat()}."
    )
    print(f"Weather locations: {', '.join(arguments.locations)}")
    print(f"Run output will be written to: {log_path}", flush=True)

    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(f"Started at: {now.isoformat()}\n")
        log_file.write(
            f"Date range: {start_date} through {end_date}\n"
        )
        log_file.write(
            f"Weather locations: {', '.join(arguments.locations)}\n"
        )

        try:
            for command in commands:
                log_file.write(
                    "\nCommand: "
                    + subprocess.list2cmdline(command)
                    + "\n"
                )
                log_file.flush()

                subprocess.run(
                    command,
                    cwd=PROJECT_DIR,
                    env=environment,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    check=True,
                )

        except (OSError, subprocess.CalledProcessError) as error:
            log_file.write(f"\nRun failed: {error}\n")
            print(f"Run failed. Open the log file: {log_path}")
            return 1

        finished_at = datetime.now(timezone.utc)

        log_file.write(
            f"\nRun completed successfully at: "
            f"{finished_at.isoformat()}\n"
        )

    print("Daily pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())