import os
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import psycopg
from dotenv import load_dotenv

from load_weather import insert_weather_rows


PROJECT_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE = "energy_warehouse_test"


class TestWeatherDatabaseLoading(unittest.TestCase):
    def connect(self) -> psycopg.Connection:
        return psycopg.connect(
            host="127.0.0.1",
            port=5432,
            dbname=TEST_DATABASE,
            user="energy",
            password=self.password,
            connect_timeout=5,
        )

    def setUp(self) -> None:
        load_dotenv(PROJECT_DIR / ".env")

        self.password = os.getenv("POSTGRES_PASSWORD")

        if not self.password:
            raise RuntimeError("POSTGRES_PASSWORD is missing")

        with self.connect() as connection:
            connection.execute("SELECT 1")

        self.location = f"test_{uuid4().hex}"
        self.start = datetime(
            2025,
            1,
            1,
            tzinfo=timezone.utc,
        )

        self.rows = [
            (
                self.location,
                self.start + timedelta(hours=hour),
                Decimal("5.00"),
                Decimal("20.00"),
                Decimal("52.520000"),
                Decimal("13.410000"),
                "integration_test.json",
            )
            for hour in range(24)
        ]

        connection_patch = patch(
            "load_weather.get_database_connection",
            side_effect=self.connect,
        )

        connection_patch.start()
        self.addCleanup(connection_patch.stop)
        self.addCleanup(self.delete_test_rows)

    def delete_test_rows(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM staging.weather_hourly
                WHERE location = %s
                """,
                (self.location,),
            )

    def read_test_rows(self) -> list[tuple]:
        with self.connect() as connection:
            return connection.execute(
                """
                SELECT
                    interval_start,
                    temperature_c,
                    wind_speed_kmh
                FROM staging.weather_hourly
                WHERE location = %s
                ORDER BY interval_start
                """,
                (self.location,),
            ).fetchall()

    def test_first_load_inserts_expected_values(self) -> None:
        changed_rows = insert_weather_rows(self.rows)
        stored_rows = self.read_test_rows()

        self.assertEqual(changed_rows, 24)
        self.assertEqual(len(stored_rows), 24)

        self.assertEqual(
            stored_rows[0],
            (
                self.start,
                Decimal("5.00"),
                Decimal("20.00"),
            ),
        )

        self.assertEqual(
            stored_rows[-1][0],
            self.start + timedelta(hours=23),
        )

    def test_repeated_load_leaves_rows_unchanged(self) -> None:
        insert_weather_rows(self.rows)
        original_rows = self.read_test_rows()

        changed_rows = insert_weather_rows(self.rows)
        stored_rows = self.read_test_rows()

        self.assertEqual(changed_rows, 0)
        self.assertEqual(len(stored_rows), 24)
        self.assertEqual(stored_rows, original_rows)

    def test_corrected_temperature_updates_one_row(self) -> None:
        insert_weather_rows(self.rows)
        original_rows = self.read_test_rows()

        corrected_rows = list(self.rows)
        corrected_first_row = list(corrected_rows[0])
        corrected_first_row[2] = Decimal("7.50")
        corrected_rows[0] = tuple(corrected_first_row)

        changed_rows = insert_weather_rows(corrected_rows)
        stored_rows = self.read_test_rows()

        self.assertEqual(changed_rows, 1)
        self.assertEqual(len(stored_rows), 24)
        self.assertEqual(
            stored_rows[0],
            (
                self.start,
                Decimal("7.50"),
                Decimal("20.00"),
            ),
        )
        self.assertEqual(stored_rows[1:], original_rows[1:])


if __name__ == "__main__":
    unittest.main()