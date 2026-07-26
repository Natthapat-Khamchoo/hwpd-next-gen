"""
Tests for Config and Station Routing (unittest runner compatible)

เทสชุดนี้กำหนด environment ของตัวเองทุกครั้ง ไม่พึ่ง .env ของเครื่องที่รัน
เพราะ app.core.config โหลด .env ให้อัตโนมัติ ถ้าปล่อยให้เทสอ่านค่าจริง
ผลเทสจะเปลี่ยนไปตามเครื่องของแต่ละคน
"""

import unittest
from unittest import mock

from app.core.config import (
    get_station_data,
    get_target_db_id,
    get_division_stations,
    check_station_match,
)

TEST_ROUTER = (
    '{"1":{"OPS":"sheet-id-for-division-1"},'
    '"5":{"OPS":"sheet-id-for-division-5"}}'
)

CONTROLLED_ENV = {
    "DB_ROUTER_JSON": TEST_ROUTER,
    "STATION_SECRETS_JSON": "",
}


class TestConfig(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", CONTROLLED_ENV, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_get_station_data(self):
        st51 = get_station_data("51")
        self.assertEqual(st51["province"], "เชียงใหม่")
        self.assertIn("กก.5", st51["fullName"])

        st11 = get_station_data("11")
        self.assertEqual(st11["province"], "อยุธยา")

    def test_get_target_db_id(self):
        self.assertEqual(get_target_db_id("51"), "sheet-id-for-division-5")
        self.assertEqual(get_target_db_id("11"), "sheet-id-for-division-1")

    def test_unconfigured_division_raises_with_its_number(self):
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
