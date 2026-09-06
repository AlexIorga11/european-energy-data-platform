import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import plotly.graph_objects as go
import psycopg
import streamlit as st
from dotenv import load_dotenv
from psycopg.rows import dict_row

from locations import DEFAULT_LOCATION, LOCATIONS, get_location
from price_rules import price_interval


PROJECT_DIR = Path(__file__).resolve().parent
HISTORY_LAG_DAYS = 7


def supports_prices(location_id):
    return get_location(location_id)["energy_zone"] is not None


def location_label(location_id):
    location = get_location(location_id)
    coverage = (
        f"prices: {location['energy_zone']} + weather"
        if supports_prices(location_id) else "weather only"
    )
    return f"{location['name']}, {location['country']} — {coverage}"


def apply_dashboard_style():
    st.markdown(
        """
        <style>
        .block-container {max-width: 1440px; padding-top: 2rem; padding-bottom: 3rem;}
        h1 {letter-spacing: -0.035em;}
        [data-testid="stMetricValue"] {font-variant-numeric: tabular-nums;}
        [data-testid="stMetricLabel"] {opacity: 0.8;}
        [data-testid="stVerticalBlockBorderWrapper"] {border-radius: 12px;}
        [data-testid="stForm"] {border-radius: 12px;}
        </style>
        """, unsafe_allow_html=True,
    )


def display_coverage():
    configured = sum(supports_prices(key) for key in LOCATIONS)
    st.caption(
        f"{len(LOCATIONS)} capitals · {configured} with a configured price zone · "
        f"{len(LOCATIONS) - configured} weather only. "
        "A configured source does not guarantee data for every date."
    )
    st.dataframe([
        {
            "Capital": location["name"],
            "Country": location["country"],
            "Price zone": location["energy_zone"] or "Not configured",
            "Coverage": "Prices + weather" if location["energy_zone"] else "Weather only",
        }
        for location in LOCATIONS.values()
    ], hide_index=True, width="stretch")
    st.caption(
        "Prices: Energy-Charts day-ahead markets, EUR/MWh. "
        "Weather: Open-Meteo. Retail tariffs are a different dataset."
    )


def query_daily_data(location_id, start_date, end_date):
    location = get_location(location_id)
    load_dotenv(PROJECT_DIR / ".env")
    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD is missing. Check the .env file.")

    zone = location["energy_zone"] if supports_prices(location_id) else None
    query = """
        WITH prices AS (
            SELECT * FROM analytics.mart_energy_daily
            WHERE zone = %s AND date_utc BETWEEN %s AND %s
        ), weather AS (
            SELECT * FROM analytics.mart_weather_daily
            WHERE location = %s AND date_utc BETWEEN %s AND %s
        )
        SELECT
            COALESCE(p.date_utc, w.date_utc) AS date_utc,
            p.avg_price_eur_per_mwh::double precision AS avg_price_eur_per_mwh,
            w.avg_temperature_c::double precision AS avg_temperature_c,
            w.avg_wind_speed_kmh::double precision AS avg_wind_speed_kmh,
            w.date_utc IS NOT NULL AS has_weather_data,
            p.interval_count AS price_interval_count,
            w.interval_count AS weather_interval_count
        FROM prices p
        FULL OUTER JOIN weather w ON p.date_utc = w.date_utc
        ORDER BY date_utc
    """
    with psycopg.connect(
        host="127.0.0.1", port=5432, dbname="energy_warehouse",
        user="energy", password=password, connect_timeout=5,
        row_factory=dict_row,
    ) as connection:
        connection.read_only = True
        with connection.cursor() as cursor:
            try:
                cursor.execute(
                    query,
                    (zone, start_date, end_date, location_id, start_date, end_date),
                )
            except psycopg.errors.UndefinedTable:
                connection.rollback()
                return []
            return cursor.fetchall()


def load_daily_data(location_id, start_date, end_date):
    for attempt in range(2):
        try:
            return query_daily_data(location_id, start_date, end_date)
        except psycopg.OperationalError as error:
            # Retry connection failures, not authentication or SQL errors.
            if error.sqlstate and not error.sqlstate.startswith("08"):
                raise
            if attempt == 1:
                raise RuntimeError(
                    "Could not connect to PostgreSQL at 127.0.0.1:5432 after "
                    "two attempts. Check Docker Desktop and run "
                    "'docker compose ps' in the project folder. "
                    f"Database details: {error}"
                ) from error
            time.sleep(1)


def expected_price_interval(location_id, start_date, end_date):
    if not supports_prices(location_id):
        return None
    return price_interval(get_location(location_id)["energy_zone"], start_date, end_date)


def remember_selection():
    # A separate value survives widget recreation during background runs.
    st.session_state["energy_saved_selection"] = (
        st.session_state["energy_city_input"],
        tuple(st.session_state["energy_dates_input"]),
    )


def initialize_selection(latest, busy):
    saved = st.session_state.get("energy_saved_selection")
    if saved is None:
        previous = st.session_state.get("energy_request")
        saved = (
            (previous[0], (previous[1], previous[2])) if previous else
            (DEFAULT_LOCATION, (latest - timedelta(days=6), latest))
        )
        st.session_state["energy_saved_selection"] = saved
    restore = st.session_state.pop("energy_restore_selection", False)
    if busy or restore or "energy_city_input" not in st.session_state:
        st.session_state["energy_city_input"] = saved[0]
    if busy or restore or "energy_dates_input" not in st.session_state:
        st.session_state["energy_dates_input"] = saved[1]


def complete_period(rows, start_date, end_date, interval_minutes):
    expected = {
        start_date + timedelta(days=i)
        for i in range((end_date - start_date).days + 1)
    }
    if len(rows) != len(expected) or {r["date_utc"] for r in rows} != expected:
        return False
    weather_complete = all(
        row["weather_interval_count"] == 24
        and row["has_weather_data"]
        and all(row[key] is not None for key in (
            "avg_temperature_c", "avg_wind_speed_kmh"
        ))
        for row in rows
    )
    if not weather_complete:
        return False
    if interval_minutes is None:
        return True
    return all(
        row["price_interval_count"] == 1440 // interval_minutes
        and row["avg_price_eur_per_mwh"] is not None
        for row in rows
    )


def build_calendar_rows(rows, start_date, end_date):
    rows_by_date = {row["date_utc"]: row for row in rows}
    calendar = []
    for offset in range((end_date - start_date).days + 1):
        day = start_date + timedelta(days=offset)
        calendar.append(rows_by_date.get(day, {
            "date_utc": day,
            "avg_price_eur_per_mwh": None,
            "avg_temperature_c": None,
            "avg_wind_speed_kmh": None,
            "has_weather_data": False,
            "price_interval_count": 0,
            "weather_interval_count": 0,
        }))
    return calendar


def build_daily_chart(rows, value_column, series_name, unit, color,
                      start_date, end_date, height=350):
    figure = go.Figure(data=[go.Scatter(
        x=[row["date_utc"] for row in rows],
        y=[row[value_column] for row in rows],
        mode="lines+markers" if len(rows) <= 31 else "lines",
        name=series_name, connectgaps=False,
        line={"color": color, "width": 2}, marker={"size": 5},
        hovertemplate="%{x|%d %b %Y}<br>%{y:.2f} " + unit + "<extra></extra>",
    )])
    figure.update_layout(
        xaxis_title="Date (UTC)", yaxis_title=f"{series_name} ({unit})",
        hovermode="x unified", height=height,
        margin={"l": 12, "r": 12, "t": 12, "b": 12},
        showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    figure.update_xaxes(type="date", showgrid=False)
    figure.update_yaxes(gridcolor="rgba(128,128,128,0.16)", zeroline=True,
                        zerolinecolor="rgba(128,128,128,0.35)")
    if start_date < end_date:
        figure.update_xaxes(range=[start_date, end_date])
    return figure


def start_pipeline(location_id, start_date, end_date, interval_minutes):
    log_dir = PROJECT_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"dashboard_{uuid4().hex}.log"
    script = "pipeline.py" if supports_prices(location_id) else "weather_pipeline.py"
    location_flag = "--locations" if supports_prices(location_id) else "--location"
    command = [
        sys.executable, "-u", str(PROJECT_DIR / script),
        "--start", start_date.isoformat(), "--end", end_date.isoformat(),
        location_flag, location_id, "--batch-days", "7",
    ]
    if supports_prices(location_id):
        command.extend(["--interval-minutes", str(interval_minutes)])
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUNBUFFERED"] = "1"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command, cwd=PROJECT_DIR, env=environment,
            stdout=log, stderr=subprocess.STDOUT,
        )
    return {"process": process, "log_path": log_path}


def read_log_tail(log_path):
    try:
        with log_path.open("rb") as log:
            log.seek(0, os.SEEK_END)
            log.seek(max(0, log.tell() - 16000))
            return log.read().decode("utf-8", errors="replace")
    except OSError:
        return "Run output is not available yet."


@st.fragment(run_every="1s")
def monitor_pipeline():
    job = st.session_state.get("energy_job")
    if job is None:
        return
    result = job["process"].poll()
    if result is None:
        st.info("Loading the selected period. The charts will appear when it finishes.")
        with st.expander("Run details"):
            st.code(read_log_tail(job["log_path"]), language="text")
        return

    st.session_state["energy_job"] = None
    st.session_state["energy_log"] = job["log_path"]
    st.session_state["energy_restore_selection"] = True
    location_id, start_date, end_date = st.session_state["energy_request"]
    if result != 0:
        st.session_state["energy_error"] = (
            "The load did not finish successfully. Open Run details for the cause. "
            "Any available data is shown below. Retry the same selection to resume."
        )
    try:
        rows = load_daily_data(location_id, start_date, end_date)
        st.session_state["energy_rows"] = rows
        interval = expected_price_interval(location_id, start_date, end_date)
        if not complete_period(rows, start_date, end_date, interval):
            st.session_state["energy_warning"] = (
                "The selected period is incomplete. Available values are shown "
                "below; missing values remain blank. Check Run details and retry."
            )
        elif result == 0:
            st.session_state["energy_notice"] = (
                f"Data loaded for {get_location(location_id)['name']}: "
                f"{start_date} to {end_date}."
            )
    except (RuntimeError, ValueError, psycopg.Error) as error:
        message = f"Could not read the updated data: {error}"
        previous_error = st.session_state.get("energy_error")
        st.session_state["energy_error"] = (
            f"{previous_error} {message}" if previous_error else message
        )
    st.rerun()


def display_charts(rows, location_id, start_date, end_date):
    location = get_location(location_id)
    calendar = build_calendar_rows(rows, start_date, end_date)
    with_prices = supports_prices(location_id)
    price_days = sum(row["avg_price_eur_per_mwh"] is not None for row in calendar)
    weather_days = sum(bool(row["has_weather_data"]) for row in calendar)
    total = len(calendar)
    st.subheader(f"{location['name']}, {location['country']}")
    scope = f"Electricity zone {location['energy_zone']}" if with_prices else "Weather overview"
    st.caption(f"{start_date:%d %b %Y} – {end_date:%d %b %Y} · {total} days · UTC · {scope}")

    metrics = []
    if with_prices:
        metrics.append(("Average price", "avg_price_eur_per_mwh", "EUR/MWh"))
    metrics.extend([
        ("Average temperature", "avg_temperature_c", "°C"),
        ("Average wind speed", "avg_wind_speed_kmh", "km/h"),
    ])
    for column, (label, field, unit) in zip(st.columns(len(metrics)), metrics):
        values = [row[field] for row in calendar if row[field] is not None]
        with column:
            with st.container(border=True):
                value = f"{sum(values) / len(values):,.2f} {unit}" if values else "N/A"
                st.metric(label, value)
                st.caption(f"{len(values)} / {total} days with values")
    st.caption("Summary cards use the mean of available daily averages. Missing days are excluded.")

    if (with_prices and price_days < total) or weather_days < total:
        st.info("Some days have no values. Gaps remain visible in the charts.")

    overview, daily_data, coverage = st.tabs(["Overview", "Daily data", "Source coverage"])
    with overview:
        if with_prices:
            with st.container(border=True):
                st.markdown("#### Daily electricity price")
                st.caption(f"Day-ahead market · {location['energy_zone']} · EUR/MWh")
                if price_days:
                    st.plotly_chart(
                        build_daily_chart(
                            calendar, "avg_price_eur_per_mwh", "Price", "EUR/MWh",
                            "#3B82F6", start_date, end_date, 400,
                        ), config={"displaylogo": False}, key="price_chart",
                        width="stretch",
                    )
                else:
                    st.info("The price source is configured, but no values were loaded for this period.")
                st.caption("Wholesale market prices. Divide EUR/MWh by 1,000 for EUR/kWh. Household tariffs differ.")
        else:
            st.caption(
                "Weather-only coverage: this project has no configured day-ahead "
                "price source for this capital."
            )
        series = [
            ("avg_temperature_c", "Temperature", "°C", "#F59E0B"),
            ("avg_wind_speed_kmh", "Wind speed", "km/h", "#14B8A6"),
        ]
        for column, (field, name, unit, color) in zip(st.columns(2), series):
            with column:
                with st.container(border=True):
                    st.markdown(f"#### {name}")
                    st.caption(f"Daily average · {location['name']} · {unit}")
                    if any(row[field] is not None for row in calendar):
                        st.plotly_chart(
                            build_daily_chart(
                                calendar, field, name, unit, color, start_date, end_date,
                            ), config={"displaylogo": False}, key=field,
                            width="stretch",
                        )
                    else:
                        st.info("No values were loaded for this period.")
        st.caption("Weather represents the selected city. Similar chart movements do not establish causation.")
    with daily_data:
        st.caption("Blank values indicate unavailable data. Missing calendar dates are added for display.")
        st.dataframe(calendar, hide_index=True, width="stretch")
    with coverage:
        display_coverage()


def main():
    st.set_page_config(page_title="European Energy Data Platform", layout="wide")
    apply_dashboard_style()
    st.caption("ENERGY & WEATHER / EUROPE")
    st.title("European Energy Data Platform")
    st.write("Explore daily electricity prices and local weather, one capital at a time.")
    latest = datetime.now(timezone.utc).date() - timedelta(days=HISTORY_LAG_DAYS)
    busy = st.session_state.get("energy_job") is not None
    location_ids = list(LOCATIONS)
    initialize_selection(latest, busy)

    with st.form("energy_selection"):
        city_column, date_column = st.columns([1.2, 1])
        with city_column:
            location_id = st.selectbox(
                "Capital and source coverage", location_ids,
                key="energy_city_input", format_func=location_label, disabled=busy,
            )
        with date_column:
            selected_dates = st.date_input(
                "Date range", key="energy_dates_input",
                min_value=date(2018, 10, 1), max_value=latest,
                format="YYYY-MM-DD", disabled=busy,
            )
        submitted = st.form_submit_button(
            "Load data", disabled=busy, on_click=remember_selection, type="primary",
        )
    st.caption(
        f"Historical dates through {latest:%d %b %Y} · UTC · "
        "A 7-day buffer is applied to recent weather. "
        "Cities marked 'weather only' have no price source configured."
    )

    if submitted and not busy:
        if len(selected_dates) != 2:
            st.error("Select both a start date and an end date.")
            return
        start_date, end_date = selected_dates
        st.session_state["energy_rows"] = None
        st.session_state["energy_error"] = None
        st.session_state["energy_notice"] = None
        st.session_state["energy_warning"] = None
        st.session_state["energy_log"] = None
        st.session_state["energy_request"] = (location_id, start_date, end_date)
        try:
            interval = expected_price_interval(location_id, start_date, end_date)
            rows = load_daily_data(location_id, start_date, end_date)
            if complete_period(rows, start_date, end_date, interval):
                st.session_state["energy_rows"] = rows
                data_kind = "Prices and weather" if supports_prices(location_id) else "Weather"
                st.session_state["energy_notice"] = (
                    f"{data_kind} for {get_location(location_id)['name']} are already stored. "
                    "No download was needed."
                )
            else:
                st.session_state["energy_job"] = start_pipeline(
                    location_id, start_date, end_date, interval,
                )
                st.rerun()
        except (OSError, ValueError, RuntimeError, psycopg.Error) as error:
            st.session_state["energy_error"] = str(error)

    if st.session_state.get("energy_job") is not None:
        monitor_pipeline()
        return
    if st.session_state.get("energy_error"):
        st.error(st.session_state["energy_error"])
    if st.session_state.get("energy_warning"):
        st.warning(st.session_state["energy_warning"])
    if st.session_state.get("energy_notice"):
        st.success(st.session_state["energy_notice"])
    if st.session_state.get("energy_log"):
        with st.expander("Run details"):
            st.code(read_log_tail(st.session_state["energy_log"]), language="text")
    rows = st.session_state.get("energy_rows")
    if rows is not None:
        display_charts(rows, *st.session_state["energy_request"])
    elif not st.session_state.get("energy_error"):
        st.info("Choose a capital and period, then press Load data.")
        with st.expander("Check source coverage before loading"):
            display_coverage()


if __name__ == "__main__":
    main()