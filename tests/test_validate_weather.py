import unittest
from copy import deepcopy
from datetime import date

from validate_weather import validate_weather


class TestValidateWeather(unittest.TestCase):
    def setUp(self) -> None:
        self.target_date = date(2025, 1, 1)

        self.valid_data = {
            "latitude": 52.52,
            "longitude": 13.41,
            "utc_offset_seconds": 0,
            "timezone": "GMT",
            "timezone_abbreviation": "GMT",
            "hourly_units": {
                "time": "iso8601",
                "temperature_2m": "°C",
                "wind_speed_10m": "km/h",
            },
            "hourly": {
                "time": [
                    f"2025-01-01T{hour:02d}:00"
                    for hour in range(24)
                ],
                "temperature_2m": [
                    float(hour)
                    for hour in range(24)
                ],
                "wind_speed_10m": [
                    float(hour + 1)
                    for hour in range(24)
                ],
            },
        }

    def test_valid_weather_data_passes(self) -> None:
        validate_weather(
            data=self.valid_data,
            target_date=self.target_date,
        )

    def test_response_must_be_json_object(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Weather response must be a JSON object",
        ):
            validate_weather(
                data=None,
                target_date=self.target_date,
            )

    def test_timezone_must_be_utc(self) -> None:
        data = deepcopy(self.valid_data)
        data["utc_offset_seconds"] = 3600

        with self.assertRaisesRegex(
            ValueError,
            "Weather data must use the UTC timezone",
        ):
            validate_weather(
                data=data,
                target_date=self.target_date,
            )

    def test_temperature_unit_must_be_celsius(self) -> None:
        data = deepcopy(self.valid_data)
        data["hourly_units"]["temperature_2m"] = "°F"

        with self.assertRaisesRegex(
            ValueError,
            "Temperature unit must be °C",
        ):
            validate_weather(
                data=data,
                target_date=self.target_date,
            )

    def test_wind_speed_unit_must_be_kilometres_per_hour(
        self,
    ) -> None:
        data = deepcopy(self.valid_data)
        data["hourly_units"]["wind_speed_10m"] = "m/s"

        with self.assertRaisesRegex(
            ValueError,
            "Wind speed unit must be km/h",
        ):
            validate_weather(
                data=data,
                target_date=self.target_date,
            )

    def test_hourly_lists_must_have_equal_lengths(self) -> None:
        data = deepcopy(self.valid_data)
        data["hourly"]["temperature_2m"].pop()

        with self.assertRaisesRegex(
            ValueError,
            "must have equal lengths",
        ):
            validate_weather(
                data=data,
                target_date=self.target_date,
            )

    def test_all_24_hours_are_required(self) -> None:
        data = deepcopy(self.valid_data)

        data["hourly"]["time"].pop()
        data["hourly"]["temperature_2m"].pop()
        data["hourly"]["wind_speed_10m"].pop()

        with self.assertRaisesRegex(
            ValueError,
            "must contain all 24 UTC hours in order",
        ):
            validate_weather(
                data=data,
                target_date=self.target_date,
            )

    def test_hours_must_be_in_correct_order(self) -> None:
        data = deepcopy(self.valid_data)

        data["hourly"]["time"][0], data["hourly"]["time"][1] = (
            data["hourly"]["time"][1],
            data["hourly"]["time"][0],
        )

        with self.assertRaisesRegex(
            ValueError,
            "must contain all 24 UTC hours in order",
        ):
            validate_weather(
                data=data,
                target_date=self.target_date,
            )

    def test_temperature_must_be_a_valid_number(self) -> None:
        data = deepcopy(self.valid_data)
        data["hourly"]["temperature_2m"][5] = None

        with self.assertRaisesRegex(
            ValueError,
            "Invalid temperature at position 5",
        ):
            validate_weather(
                data=data,
                target_date=self.target_date,
            )

    def test_wind_speed_must_be_a_valid_number(self) -> None:
        data = deepcopy(self.valid_data)
        data["hourly"]["wind_speed_10m"][7] = "fast"

        with self.assertRaisesRegex(
            ValueError,
            "Invalid wind speed at position 7",
        ):
            validate_weather(
                data=data,
                target_date=self.target_date,
            )

    def test_wind_speed_cannot_be_negative(self) -> None:
        data = deepcopy(self.valid_data)
        data["hourly"]["wind_speed_10m"][10] = -1.0

        with self.assertRaisesRegex(
            ValueError,
            "Wind speed cannot be negative at position 10",
        ):
            validate_weather(
                data=data,
                target_date=self.target_date,
            )


if __name__ == "__main__":
    unittest.main()