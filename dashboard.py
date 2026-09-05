import os
from pathlib import Path

import plotly.graph_objects as go
import psycopg
import streamlit as st
from dotenv import load_dotenv
from psycopg.rows import dict_row


PROJECT_DIR = Path(__file__).resolve().parent


def load_daily_data() -> list[dict]:
    load_dotenv(PROJECT_DIR / ".env")

    password = os.getenv("POSTGRES_PASSWORD")

    if not password:
        raise RuntimeError(
            "POSTGRES_PASSWORD is missing. Check the .env file."
        )

    query = """
        SELECT
            date_utc,
            avg_price_eur_per_mwh::double precision
                AS avg_price_eur_per_mwh,
            avg_temperature_c::double precision
                AS avg_temperature_c,
            avg_wind_speed_kmh::double precision
                AS avg_wind_speed_kmh,
            has_weather_data
        FROM analytics.mart_energy_weather_daily
        WHERE zone = %s
            AND weather_location = %s
        ORDER BY date_utc
    """

    with psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname="energy_warehouse",
        user="energy",
        password=password,
        connect_timeout=5,
        row_factory=dict_row,
    ) as connection:
        connection.read_only = True

        with connection.cursor() as cursor:
            cursor.execute(query, ("DE-LU", "berlin"))
            return cursor.fetchall()


def build_daily_chart(
    rows: list[dict],
    value_column: str,
    series_name: str,
    unit: str,
    color: str,
    start_date,
    end_date,
    height: int = 350,
) -> go.Figure:
    figure = go.Figure(
        data=[
            go.Scatter(
                x=[row["date_utc"] for row in rows],
                y=[row[value_column] for row in rows],
                mode="lines+markers",
                name=series_name,
                connectgaps=False,
                line={"color": color, "width": 2},
                marker={"size": 5},
                hovertemplate=(
                    "%{x|%d %b %Y}"
                    "<br>%{y:.2f} "
                    + unit
                    + "<extra></extra>"
                ),
            )
        ]
    )

    figure.update_layout(
        xaxis_title="Date (UTC)",
        yaxis_title=f"{series_name} ({unit})",
        hovermode="x unified",
        height=height,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
    )

    figure.update_xaxes(type="date")

    if start_date < end_date:
        figure.update_xaxes(range=[start_date, end_date])

    return figure


def main() -> None:
    st.set_page_config(
        page_title="European Energy Data Platform",
        layout="wide",
    )

    st.title("European Energy Data Platform")
    st.caption(
        "DE-LU day-ahead electricity prices. "
        "Weather location: Berlin. Dates use UTC."
    )

    try:
        rows = load_daily_data()
    except (RuntimeError, psycopg.Error) as error:
        st.error("Could not load dashboard data.")

        with st.expander("Error details"):
            st.code(str(error))

        st.stop()

    if not rows:
        st.info(
            "No daily data is available yet. "
            "Run the pipeline before opening the dashboard."
        )
        st.stop()

    first_day = rows[0]["date_utc"]
    last_day = rows[-1]["date_utc"]

    selected_dates = st.date_input(
        "Date range",
        value=(first_day, last_day),
        min_value=first_day,
        max_value=last_day,
        format="YYYY-MM-DD",
    )

    if len(selected_dates) != 2:
        st.info("Select both a start date and an end date.")
        st.stop()

    start_date, end_date = selected_dates

    selected_rows = [
        row
        for row in rows
        if start_date <= row["date_utc"] <= end_date
    ]

    if not selected_rows:
        st.info("No data is available for this date range.")
        st.stop()

    weather_days = sum(
        row["has_weather_data"]
        for row in selected_rows
    )

    days_column, weather_column = st.columns(2)

    days_column.metric(
        "Days with prices",
        len(selected_rows),
    )

    weather_column.metric(
        "Days with weather",
        weather_days,
    )

    st.subheader("Daily average electricity price")

    price_chart = build_daily_chart(
        rows=selected_rows,
        value_column="avg_price_eur_per_mwh",
        series_name="Price",
        unit="EUR/MWh",
        color="#2563EB",
        start_date=start_date,
        end_date=end_date,
        height=400,
    )

    st.plotly_chart(
        price_chart,
        config={"displaylogo": False},
        key="price_chart",
    )

    st.caption(
        "Wholesale prices in EUR/MWh, not household tariffs. "
        "Divide by 1,000 to convert to EUR/kWh."
    )

    st.subheader("Weather in Berlin")
    st.caption(
        "Weather data represents Berlin, not the entire DE-LU zone. "
        "Similar movements in the charts do not establish causation."
    )

    if weather_days == 0:
        st.info("No weather data is available for this date range.")
    else:
        if weather_days < len(selected_rows):
            st.info(
                "Weather data is missing for "
                f"{len(selected_rows) - weather_days} days. "
                "Missing values appear as gaps in the charts."
            )

        temperature_column, wind_column = st.columns(2)

        with temperature_column:
            st.markdown("#### Daily average temperature")

            temperature_chart = build_daily_chart(
                rows=selected_rows,
                value_column="avg_temperature_c",
                series_name="Temperature",
                unit="°C",
                color="#EA580C",
                start_date=start_date,
                end_date=end_date,
            )

            st.plotly_chart(
                temperature_chart,
                config={"displaylogo": False},
                key="temperature_chart",
            )

        with wind_column:
            st.markdown("#### Daily average wind speed")

            wind_chart = build_daily_chart(
                rows=selected_rows,
                value_column="avg_wind_speed_kmh",
                series_name="Wind speed",
                unit="km/h",
                color="#0D9488",
                start_date=start_date,
                end_date=end_date,
            )

            st.plotly_chart(
                wind_chart,
                config={"displaylogo": False},
                key="wind_chart",
            )

    with st.expander("View daily data"):
        st.dataframe(
            selected_rows,
            hide_index=True,
        )


if __name__ == "__main__":
    main()