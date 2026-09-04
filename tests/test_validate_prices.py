import unittest

from validate_prices import validate_prices


class TestValidatePrices(unittest.TestCase):
    def setUp(self):
        self.date_utc = "2025-01-01"
        self.start_timestamp = 1735689600

        self.data = {
            "unix_seconds": [
                self.start_timestamp + hour * 3600
                for hour in range(24)
            ],
            "price": [10.0, -1.5, 0.0] + [20.0] * 21,
            "unit": "EUR / MWh",
        }

    def test_accepts_valid_prices(self):
        record_count = validate_prices(self.data, self.date_utc)

        self.assertEqual(record_count, 24)

    def test_rejects_missing_price(self):
        self.data["price"][0] = None

        with self.assertRaisesRegex(ValueError, "Invalid price"):
            validate_prices(self.data, self.date_utc)

    def test_rejects_different_array_lengths(self):
        self.data["price"].pop()

        with self.assertRaisesRegex(ValueError, "counts do not match"):
            validate_prices(self.data, self.date_utc)

    def test_rejects_duplicate_timestamps(self):
        self.data["unix_seconds"][1] = self.data["unix_seconds"][0]

        with self.assertRaisesRegex(ValueError, "Duplicate timestamps"):
            validate_prices(self.data, self.date_utc)

    def test_rejects_unordered_timestamps(self):
        self.data["unix_seconds"].reverse()

        with self.assertRaisesRegex(ValueError, "chronological order"):
            validate_prices(self.data, self.date_utc)

    def test_rejects_timestamp_outside_requested_day(self):
        self.data["unix_seconds"][-1] = 1735776000

        with self.assertRaisesRegex(ValueError, "outside the requested UTC day"):
            validate_prices(self.data, self.date_utc)

    def test_rejects_unexpected_unit(self):
        self.data["unit"] = "EUR / kWh"

        with self.assertRaisesRegex(ValueError, "Unexpected price unit"):
            validate_prices(self.data, self.date_utc)

    def test_rejects_missing_first_interval(self):
        self.data["unix_seconds"].pop(0)
        self.data["price"].pop(0)

        with self.assertRaisesRegex(ValueError, "1 missing intervals"):
            validate_prices(self.data, self.date_utc)

    def test_rejects_missing_middle_interval(self):
        self.data["unix_seconds"].pop(12)
        self.data["price"].pop(12)

        with self.assertRaisesRegex(ValueError, "1 missing intervals"):
            validate_prices(self.data, self.date_utc)

    def test_rejects_missing_last_interval(self):
        self.data["unix_seconds"].pop()
        self.data["price"].pop()

        with self.assertRaisesRegex(ValueError, "1 missing intervals"):
            validate_prices(self.data, self.date_utc)

    def test_accepts_explicit_fifteen_minute_resolution(self):
        self.data["unix_seconds"] = [
            self.start_timestamp + interval * 900
            for interval in range(96)
        ]
        self.data["price"] = [10.0] * 96

        record_count = validate_prices(
            self.data,
            self.date_utc,
            expected_interval_seconds=900,
        )

        self.assertEqual(record_count, 96)


if __name__ == "__main__":
    unittest.main()