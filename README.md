# European Energy Data Platform

A local data pipeline for collecting electricity prices from Energy-Charts,
loading validated records into PostgreSQL, and building daily analytics
with dbt.

The current implementation processes the Germany–Luxembourg bidding zone
(`DE-LU`). Date ranges and daily aggregations use UTC.

## How it works

1. Read the requested date range.
2. Reuse valid local JSON files or download missing data.
3. Validate timestamps, prices, and units.
4. Insert new records into PostgreSQL and update changed values.
5. Build daily price statistics with dbt.
6. Run dbt data tests.

Raw responses are saved as JSON under:

```text
data/raw/energy_charts/zone=DE-LU/YYYY-MM-DD.json
```

These files allow a failed load to be retried without downloading the
same data again.

## Stack

- Python: API requests, validation, and pipeline execution
- PostgreSQL 17: storage
- Docker Compose: local PostgreSQL service and persistent volume
- dbt Core with dbt-postgres: SQL transformations and data tests
- unittest: Python validation tests

## Data model

### staging.energy_prices

One record per bidding zone and interval.

| Column | Purpose |
|---|---|
| zone | Bidding zone identifier |
| interval_start | Interval start as a timezone-aware timestamp |
| price_eur_per_mwh | Electricity price in EUR/MWh |
| source_file | Relative path to the source JSON file |
| loaded_at | Timestamp of insertion or the latest value change |

The primary key is `(zone, interval_start)`.

Loading the same file again leaves identical records unchanged.
If the price or source-file path changes, the existing record is updated.

### analytics.mart_energy_daily

One record per bidding zone and UTC date.

| Column | Purpose |
|---|---|
| zone | Bidding zone identifier |
| date_utc | UTC date |
| interval_count | Number of available price intervals |
| avg_price_eur_per_mwh | Arithmetic mean of available interval prices |
| min_price_eur_per_mwh | Lowest available interval price |
| max_price_eur_per_mwh | Highest available interval price |

dbt rebuilds this table from all records in staging on each pipeline run.
The average is not weighted by electricity consumption.

## Local setup

The commands below use Windows PowerShell and should be run from the
repository root.

### Prerequisites

- Python 3.13
- Git
- Docker Desktop running Linux containers

### Create the Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Configure the database password

Create a `.env` file in the repository root:

```dotenv
POSTGRES_PASSWORD=replace_with_a_local_password
```

Docker Compose, the Python loader, and the dbt launcher use this password.
The `.env` file is excluded from Git.

The PostgreSQL container applies this password when it first initializes
an empty data volume. Editing `.env` later does not change the password
of an existing database.

### Start PostgreSQL

```powershell
docker compose up -d --wait
```

PostgreSQL is exposed on `127.0.0.1:5432`.

Create the staging schema and table:

```powershell
docker compose cp ./sql/create_tables.sql postgres:/tmp/create_tables.sql
docker compose exec postgres psql -U energy -d energy_warehouse -v ON_ERROR_STOP=1 --single-transaction -f /tmp/create_tables.sql
```

### Check connections

```powershell
python database.py
python run_dbt.py debug
```

## Run the pipeline

```powershell
python pipeline.py --start 2025-01-01 --end 2025-01-04
```

Both dates are inclusive.

The pipeline loads each requested day, then runs `dbt build` to rebuild
the daily model and execute its data tests.

Run the same command again to reuse valid local files. Identical staging
records are not inserted or updated again.

To download the requested dates again:

```powershell
python pipeline.py --start 2025-01-01 --end 2025-01-04 --refresh
```

A refreshed download overwrites the existing raw file for that date.

## Inspect the results

```powershell
docker compose exec postgres psql -U energy -d energy_warehouse -c "SELECT * FROM analytics.mart_energy_daily ORDER BY zone, date_utc;"
```

The January 1–4, 2025 example was verified locally with:

- 96 staging records
- 4 daily rows
- 24 intervals per day

These counts describe this example, not a rule for every date.

## Tests

Run the Python validation tests:

```powershell
python -m unittest discover -s tests -v
```

The seven tests cover valid prices, missing prices, mismatched array
lengths, duplicate timestamps, timestamp ordering, timestamps outside
the requested day, and unexpected units.

Run the dbt data tests against the existing daily table:

```powershell
python run_dbt.py test
```

The seven dbt tests check:

- No null values in the six daily-model columns
- No duplicate combinations of zone and UTC date

To rebuild the model and run its tests:

```powershell
python run_dbt.py build
```

## Failure handling

- HTTP 429 responses are retried up to three total attempts.
- Retry delays account for the Retry-After header when available.
- Invalid cached files trigger a new download.
- Data is validated before being written to PostgreSQL.
- Each daily load runs in a database transaction.
- A dbt failure causes the pipeline to exit with an error.

The complete pipeline is not one database transaction. Previously
committed daily loads remain stored if a later step fails.

A failed dbt data test does not automatically restore the previous
version of the analytics table.

## Current limitations

- Only DE-LU is supported by the pipeline.
- Missing intervals and entirely missing days are not checked automatically.
- Existing tests do not independently verify aggregation arithmetic.
- Raw files are overwritten on refresh; historical response versions are
  not retained.
- HTTP errors other than 429 and network failures are not retried.
- Database loads upsert supplied records; records absent from a refreshed
  response are not automatically deleted.
- The daily model is fully rebuilt rather than incrementally updated.
- Execution is manual; scheduling and CI are not configured.
- The database uses a local development user rather than separate
  least-privilege roles.

## Stop the database

```powershell
docker compose stop
```

The database files remain in the named Docker volume.

## Data source

Electricity prices are retrieved from the
[Energy-Charts API](https://api.energy-charts.info/).

The saved response includes the source and licensing metadata returned
by the API. Review that metadata before redistributing data.