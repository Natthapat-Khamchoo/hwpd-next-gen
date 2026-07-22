"""
Tests for Config and Station Routing (unittest runner compatible)
"""

import unittest
from app.core.config import (
    get_station_data,
    get_target_db_id,
    get_division_stations,
    check_station_match,
)


class TestConfig(unittest.TestCase):
    def test_get_station_data(self):
        st51 = get_station_data("51")
        self.assertEqual(st51["province"], "เชียงใหม่")
        self.assertIn("กก.5", st51["fullName"])

        st11 = get_station_data("11")
        self.assertEqual(st11["province"], "อยุธยา")

    def test_get_target_db_id(self):
        db5 = get_target_db_id("51")
        self.assertEqual(db5, "1R0x-rH8hfH9OXhtwVgxc9KKXv_d4xPYK1-0Sn13jkgA")

        db1 = get_target_db_id("11")
        self.assertEqual(db1, "1Sgji6GHkgY1dlFei9jTiaW67-VFIu7zAf13PfwumQBc")

        with self.assertRaises(ValueError) as ctx:
            get_target_db_id("21")
        self.assertIn("กองกำกับการ 2", str(ctx.exception))

    def test_get_division_stations(self):
        stations_div5 = get_division_stations("51", include_hq=False)
        self.assertIn("51", stations_div5)
        self.assertIn("56", stations_div5)
        self.assertNotIn("50", stations_div5)

        stations_div5_hq = get_division_stations("51", include_hq=True)
        self.assertIn("50", stations_div5_hq)

    def test_check_station_match(self):
        self.assertTrue(check_station_match("51", "51"))
        self.assertTrue(check_station_match("00", "51"))
        self.assertTrue(check_station_match("HQ", "12"))
        self.assertTrue(check_station_match("50", "51"))
        self.assertTrue(check_station_match("50", "56"))
        self.assertFalse(check_station_match("50", "11"))
        self.assertFalse(check_station_match("51", "52"))


if __name__ == "__main__":
    unittest.main()
