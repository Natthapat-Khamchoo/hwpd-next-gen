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
        self.assertEqual(st51["province"], "ตาก")
        self.assertEqual(st51["fullName"], "ส.ทล.1 กก.5 บก.ทล.")
        self.assertIn("แม่สอด", st51["units"])

        st11 = get_station_data("11")
        self.assertEqual(st11["province"], "อยุธยา")

    def test_fullname_uses_second_digit_as_station_number(self):
        # "86" คือ ส.ทล.6 กก.8 ไม่ใช่ ส.ทล.86 — เคยพลาดตรงนี้ตอนที่ยังไม่มีข้อมูล กก.2-4, 6-8
        self.assertEqual(get_station_data("86")["fullName"], "ส.ทล.6 กก.8 บก.ทล.")

    def test_division_hq_is_not_labelled_as_a_station(self):
        self.assertEqual(get_station_data("70")["fullName"], "ฝอ.กก.7 บก.ทล.")
        self.assertEqual(get_station_data("70")["units"], ["ฝอ.กก.7"])

    def test_every_division_has_its_stations_configured(self):
        expected = {"1": 6, "2": 6, "3": 5, "4": 5, "5": 6, "6": 6, "7": 5, "8": 4}
        for division, count in expected.items():
            stations = get_division_stations(f"{division}1", include_hq=False)
            self.assertEqual(len(stations), count, f"กก.{division} ควรมี {count} สถานี")
            for station_id in stations:
                data = get_station_data(station_id)
                self.assertTrue(data["units"], f"สถานี {station_id} ไม่มีหน่วยบริการ")
                self.assertNotIn("กองกำกับการ", data["province"], f"สถานี {station_id} ยังไม่ได้ตั้งจังหวัด")

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
