# European Energy Data Platform

A local data pipeline that combines day-ahead electricity prices from
Energy-Charts with historical weather data from Open-Meteo.

Python downloads and validates the data, PostgreSQL stores hourly records,
dbt builds daily analytics, and a Streamlit dashboard displays the results.

The project currently uses the Germany–Luxembourg bidding zone (`DE-LU`)
and weather data for Berlin. All processing dates and daily aggregations
use UTC.

## Dashboard

![Dashboard showing DE-LU electricity prices above Berlin temperature and wind charts](docs/images/dashboard.png)

The dashboard includes:

- Daily average electricity prices in EUR/MWh
- Daily average temperature in Berlin in °C
- Daily average wind speed in Berlin in km/h
- A shared date-range filter
- Counts of days with price and weather data
- A table of the underlying daily results

The dashboard reads from PostgreSQL. Opening it does not download new
data or run the pipeline.

Berlin weather is a local reference, not a measurement of conditions
across the entire DE-LU zone. The charts support exploration; they do not
establish that weather changes caused price changes.

## Stack

| Component | Purpose |
|---|---|
| Python 3.13 | API requests, validation, and pipeline execution |
| PostgreSQL 17 | Storage and SQL analytics |
| Docker Compose | Local database service and persistent storage |
| dbt Core with dbt-postgres | Transformations and data tests |
| unittest | Python validation tests |
| Streamlit | Local dashboard |
| Plotly | Interactive charts |
| GitHub Actions | Automated Python and dbt checks |

## Pipeline behavior

For each requested UTC day, the pipeline:

1. Reuses valid cached data or downloads a new response.
2. Validates timestamps, units, completeness, and numeric values.
3. Loads electricity prices and weather into PostgreSQL.
4. Inserts new records and updates records whose values have changed.

After processing the date range, it runs `dbt build` to rebuild the
analytics tables and execute their tests.

Raw JSON files are stored under:

```text
data/raw/energy_charts/zone=DE-LU/YYYY-MM-DD.json
data/raw/open_meteo/location=berlin/YYYY-MM-DD.json
```

The `data/` directory is excluded from Git. Cached responses allow
database loads to be retried without downloading the same data again.

## Data model

| Table | One row represents |
|---|---|
| `staging.energy_prices` | One price interval for a bidding zone |
| `staging.weather_hourly` | One weather hour for a location |
| `analytics.mart_energy_daily` | One bidding zone and UTC date |
| `analytics.mart_weather_daily` | One location and UTC date |
| `analytics.mart_energy_weather_daily` | One DE-LU date associated with Berlin weather |

The staging tables use composite primary keys:

- Prices: `(zone, interval_start)`
- Weather: `(location, interval_start)`

Both loaders use upserts. Loading identical data again leaves existing
records unchanged.

The daily models calculate averages, minimums, maximums, and interval
counts. Price averages are arithmetic means of interval prices, not
weighted by electricity consumption.

The combined model uses a left join from daily energy prices to daily
weather. Days with prices remain present when weather is unavailable.
Missing weather stays `NULL`, and `has_weather_data` indicates whether
a matching weather row exists.

## Local setup

Run the following commands in Windows PowerShell from the repository root.

### Prerequisites

- Python 3.13
- Git
- Docker Desktop running Linux containers

### Clone the repository

```powershell
git clone https://github.com/AlexIorga11/european-energy-data-platform.git
cd european-energy-data-platform
```

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

Docker Compose, the Python components, and the dbt launcher use this
password. The `.env` file is excluded from Git.

PostgreSQL applies the configured password when it initializes an empty
data volume. Editing `.env` later does not change the password of an
existing database.

### Start PostgreSQL

Make sure Docker Desktop is running, then execute:

```powershell
docker compose up -d --wait
```

PostgreSQL is exposed on `127.0.0.1:5432`.

Create the staging tables:

```powershell
docker compose cp ./sql/create_tables.sql postgres:/tmp/create_tables.sql
docker compose exec postgres psql -U energy -d energy_warehouse -v ON_ERROR_STOP=1 --single-transaction -f /tmp/create_tables.sql
```

Check the connection:

```powershell
python run_dbt.py debug
```

## Run the pipeline

Start with a small date range:

```powershell
python pipeline.py --start 2025-01-01 --end 2025-01-04
```

Both dates are inclusive.

To load January 2025:

```powershell
python pipeline.py --start 2025-01-01 --end 2025-01-31
```

A complete January load should contain:

- 744 hourly price records
- 744 hourly weather records
- 31 rows in each daily model

These counts describe this example and its hourly resolution.

Run the same command again to reuse valid cached files. Identical
staging records will not be inserted or updated again.

To download the requested period again:

```powershell
python pipeline.py --start 2025-01-01 --end 2025-01-04 --refresh
```

Refresh replaces the existing raw files for those dates.

### Price interval resolution

Price validation expects 60-minute intervals by default. For a period
where the source supplies 15-minute prices, specify:

```powershell
python pipeline.py --start 2026-01-01 --end 2026-01-01 --interval-minutes 15
```

This option tells the validator which resolution to expect. It does not
resample data or change the API response. Weather remains hourly.

## Run the dashboard

After loading data and building the dbt models:

```powershell
python -m streamlit run dashboard.py --server.address 127.0.0.1
```

Open the local URL printed in the terminal, normally:

```text
http://localhost:8501
```

Keep the terminal and PostgreSQL running while using the dashboard.
Press `Ctrl+C` in the dashboard terminal to stop it.

Prices are displayed in EUR/MWh. Divide by 1,000 to convert to EUR/kWh.
These are wholesale electricity prices, not household tariffs.

## Inspect the results

Check the date range and weather coverage:

```powershell
docker compose exec postgres psql -U energy -d energy_warehouse -c "SELECT COUNT(*) AS total_days, COUNT(*) FILTER (WHERE has_weather_data) AS days_with_weather, MIN(date_utc) AS first_day, MAX(date_utc) AS last_day FROM analytics.mart_energy_weather_daily;"
```

View daily prices and weather:

```powershell
docker compose exec postgres psql -U energy -d energy_warehouse -c "SELECT date_utc, avg_price_eur_per_mwh, avg_temperature_c, avg_wind_speed_kmh, has_weather_data FROM analytics.mart_energy_weather_daily ORDER BY date_utc;"
```

## Tests and continuous integration

Run the Python tests:

```powershell
python -m unittest discover -s tests -v
```

The current suite contains 22 validation tests covering energy and
weather data, including missing intervals, invalid values, unexpected
units, ordering, and mismatched array lengths.

Build the analytics tables and run dbt tests:

```powershell
python run_dbt.py build
```

The current dbt project contains:

- 3 table models
- 19 data tests
- 1 unit test for the daily energy aggregation

A complete successful build reports 23 operations. This count includes
model builds, not just tests.

Data tests check null values, duplicate daily keys, preservation of
energy dates in the combined model, and consistency between weather
availability and weather columns.

GitHub Actions runs on pushes and pull requests. It installs dependencies,
starts a temporary PostgreSQL service, runs Python tests, creates staging
tables, checks the dbt connection, and executes `dbt build`.

CI does not call the external data APIs or load a historical dataset.
Data tests against empty tables do not establish that production data
exists. Local pipeline runs and SQL checks verify actual loaded results.
Dashboard behavior is currently checked manually.

## Failure handling

- Rate-limited requests are retried with a delay.
- Invalid cached files trigger a new download.
- Validation runs before a daily database load.
- Each daily load uses a database transaction.
- Identical rows remain unchanged on repeated loads.
- A dbt failure prevents the pipeline from reporting success.

The complete pipeline is not a single transaction. If a later step fails,
previously committed daily loads remain stored. The same date range can
be rerun to retry the remaining work.

A failed dbt data test does not automatically restore an earlier version
of an analytics table.

## Current limitations

- The pipeline supports DE-LU prices and Berlin weather.
- Historical downloads make separate daily requests and may encounter
  API rate limits.
- A valid cached file is reused until a refresh is requested; upstream
  revisions are not detected automatically.
- Raw response versions are not retained after a refresh.
- Upserts do not delete records absent from a refreshed response.
- Daily analytics tables are fully rebuilt.
- Execution is manual; scheduling is not implemented.
- CI does not yet test database loader behavior with sample records.
- Weather aggregation arithmetic does not yet have a dedicated unit test.
- Dashboard interactions query the daily table again; caching and
  server-side date filtering are not implemented.
- The dashboard uses a read-only database transaction, but shares the
  local development database credentials with the pipeline.

## Stop PostgreSQL

```powershell
docker compose stop
```

Database files remain in the named Docker volume.

## Data sources

- [Energy-Charts API](https://api.energy-charts.info/):
  day-ahead electricity prices for DE-LU.
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api):
  historical weather data for Berlin.

Open-Meteo historical weather uses gridded model and reanalysis data;
it is not necessarily a direct observation from a weather station at
the requested coordinates.

Review the providers' attribution and licensing requirements before
redistributing downloaded data.