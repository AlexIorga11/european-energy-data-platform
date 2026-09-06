import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import psycopg
from streamlit.testing.v1 import AppTest

import dashboard


START = date(2026, 8, 24)
END = date(2026, 8, 30)


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        instant = cls(2026, 9, 6, 12, tzinfo=timezone.utc)
        return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)


def daily_rows(with_prices=True):
    return [
        {
            "date_utc": START + timedelta(days=offset),
            "avg_price_eur_per_mwh": 80.0 + offset if with_prices else None,
            "avg_temperature_c": 20.0 + offset,
            "avg_wind_speed_kmh": 10.0,
            "has_weather_data": True,
            "price_interval_count": 96 if with_prices else None,
            "weather_interval_count": 24,
        }
        for offset in range(7)
    ]


class DashboardInteractionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.log_path = Path(temporary.name) / "pipeline.log"
        self.log_path.write_text("Simulated pipeline output\n", encoding="utf-8")

        self.read = self.start_patch("load_daily_data", return_value=[])
        self.launch = self.start_patch("start_pipeline")
        self.start_patch("datetime", new=FixedDateTime)
        self.start_patch(
            "psycopg.connect",
            side_effect=AssertionError("Dashboard tests must not access PostgreSQL"),
        )
        self.start_patch(
            "subprocess.Popen",
            side_effect=AssertionError("Dashboard tests must not launch a pipeline"),
        )
        self.app = AppTest.from_string(
            "import dashboard\ndashboard.main()", default_timeout=15,
        ).run()
        self.assert_no_errors()

    def start_patch(self, name, **kwargs):
        patcher = patch(f"dashboard.{name}", **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def assert_no_errors(self):
        self.assertEqual(len(self.app.exception), 0, str(list(self.app.exception)))

    def submit(self, city):
        self.app.selectbox(key="energy_city_input").select(city)
        self.app.date_input(key="energy_dates_input").set_value((START, END))
        self.app.button[0].click().run()
        self.assert_no_errors()

    def begin_download(self, city):
        self.read.return_value = []
        process = Mock()
        process.poll.return_value = None
        self.launch.return_value = {"process": process, "log_path": self.log_path}
        self.submit(city)
        return process

    def finish_download(self, process, rows, exit_code=0):
        self.read.return_value = rows
        process.poll.return_value = exit_code
        self.app.run()
        self.assert_no_errors()

    def test_city_and_dates_survive_consecutive_downloads(self):
        for city in ("bucharest", "baku", "paris"):
            with self.subTest(city=city):
                process = self.begin_download(city)
                self.assertEqual(self.app.selectbox[0].value, city)
                self.assertTrue(self.app.selectbox[0].disabled)
                self.assertEqual(tuple(self.app.date_input[0].value), (START, END))

                self.finish_download(process, daily_rows(city != "baku"))
                self.assertEqual(self.app.selectbox[0].value, city)
                self.assertFalse(self.app.selectbox[0].disabled)
                self.assertEqual(tuple(self.app.date_input[0].value), (START, END))
                self.read.assert_called_with(city, START, END)
                expected_name = dashboard.get_location(city)["name"]
                self.assertTrue(any(
                    expected_name in heading.value for heading in self.app.subheader
                ))
                self.assertEqual(len(self.app.success), 1)

    def test_repeated_search_reuses_stored_data(self):
        process = self.begin_download("bucharest")
        self.finish_download(process, daily_rows())
        self.submit("bucharest")
        self.launch.assert_called_once()
        self.assertIn("No download was needed", self.app.success[0].value)
        self.assertEqual(len(self.app.get("plotly_chart")), 3)

    def test_weather_only_city_is_complete_without_prices(self):
        self.read.return_value = daily_rows(with_prices=False)
        self.submit("baku")
        self.launch.assert_not_called()
        self.assertEqual(len(self.app.get("plotly_chart")), 2)
        self.assertEqual(len(self.app.warning), 0)
        self.assertIn("Weather for Baku", self.app.success[0].value)

    def test_incomplete_data_does_not_show_success(self):
        incomplete_intervals = daily_rows()
        incomplete_intervals[0]["price_interval_count"] = 95
        cases = [[], daily_rows()[:3], incomplete_intervals]
        for rows in cases:
            with self.subTest(days=len(rows)):
                process = self.begin_download("bucharest")
                self.finish_download(process, rows)
                self.assertEqual(len(self.app.success), 0)
                self.assertEqual(len(self.app.warning), 1)
                self.assertEqual(self.app.session_state["energy_rows"], rows)

    def test_failed_download_keeps_available_data(self):
        process = self.begin_download("bucharest")
        rows = daily_rows()[:3]
        self.finish_download(process, rows, exit_code=1)
        self.assertEqual(len(self.app.success), 0)
        self.assertEqual(len(self.app.error), 1)
        self.assertEqual(self.app.session_state["energy_rows"], rows)
        self.assertEqual(len(self.app.get("plotly_chart")), 3)


class DashboardDataTests(unittest.TestCase):
    def test_missing_day_remains_a_gap_in_the_chart(self):
        rows = daily_rows()
        del rows[2]
        calendar = dashboard.build_calendar_rows(rows, START, END)
        figure = dashboard.build_daily_chart(
            calendar, "avg_price_eur_per_mwh", "Price", "EUR/MWh",
            "#3B82F6", START, END,
        )
        self.assertEqual(len(calendar), 7)
        self.assertEqual(calendar[2]["date_utc"], START + timedelta(days=2))
        self.assertIsNone(figure.data[0].y[2])
        self.assertFalse(figure.data[0].connectgaps)
        self.assertEqual(len(rows), 6)

    def test_weather_only_download_uses_weather_pipeline(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(dashboard, "PROJECT_DIR", Path(temporary)):
                with patch.object(dashboard.subprocess, "Popen") as launch:
                    job = dashboard.start_pipeline("baku", START, END, None)
        command = launch.call_args.args[0]
        self.assertEqual(Path(command[2]).name, "weather_pipeline.py")
        self.assertEqual(command[command.index("--location") + 1], "baku")
        self.assertNotIn("--interval-minutes", command)
        self.assertIs(job["process"], launch.return_value)

    def test_temporary_database_failure_is_retried(self):
        with patch.object(dashboard, "query_daily_data") as query:
            query.side_effect = [psycopg.OperationalError("timeout"), daily_rows()]
            with patch.object(dashboard.time, "sleep"):
                result = dashboard.load_daily_data("bucharest", START, END)
        self.assertEqual(result, daily_rows())
        self.assertEqual(query.call_count, 2)

    def test_persistent_database_failure_stops_after_two_attempts(self):
        with patch.object(dashboard, "query_daily_data") as query:
            query.side_effect = psycopg.OperationalError("timeout")
            with patch.object(dashboard.time, "sleep"):
                with self.assertRaisesRegex(RuntimeError, "two attempts"):
                    dashboard.load_daily_data("bucharest", START, END)
        self.assertEqual(query.call_count, 2)

    def test_wrong_database_password_is_not_retried(self):
        with patch.object(dashboard, "query_daily_data") as query:
            query.side_effect = psycopg.errors.InvalidPassword("wrong password")
            with patch.object(dashboard.time, "sleep"):
                with self.assertRaises(psycopg.errors.InvalidPassword):
                    dashboard.load_daily_data("bucharest", START, END)
        query.assert_called_once()


if __name__ == "__main__":
    unittest.main()
