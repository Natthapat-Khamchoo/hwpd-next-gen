"""
แก้ข้อมูลผู้ใช้ต้องแตะเฉพาะช่องที่ส่งมา และเฉพาะช่องที่อนุญาต

`tb_Users` เป็นตารางที่ระบบล็อกอินอ่าน เขียนพลาดช่องเดียวคือมีคนเข้าระบบไม่ได้
หรือแย่กว่านั้นคือได้สิทธิ์ผิดหน่วย เทสชุดนี้จึงล็อกขอบเขตการเขียนไว้
"""

import unittest
from unittest import mock

from app.services import user_service

HEADER = [
    "Username", "Password", "FullName", "Station_ID", "Unit_ID", "Role",
    "สถานะไปช่วยราชการ", "สถานะมาช่วยราชการ", "หมายเหตุ", "เบอร์โทร",
    "รหัส", "วันที่เริ่มช่วยราชการ", "วันที่สิ้นสุดช่วยราชการ", "AccountType",
]
ROWS = [
    HEADER,
    ["op111", "sha256$x", "(รอระบุชื่อ) ส.ทล.1 กก.1", "11", "วังน้อย", "Unit_Staff",
     "", "", "", "", "", "", "", ""],
    ["st11", "sha256$y", "ส.ทล.1 กก.1 บก.ทล.", "11", "วังน้อย", "Station_Admin",
     "", "", "", "", "", "", "", "Unit"],
]


class TestUpdateProfile(unittest.TestCase):
    def setUp(self):
        self.worksheet = mock.Mock()
        self.patches = [
            mock.patch.object(user_service.sheets_service, "read_table", return_value=ROWS),
            mock.patch.object(user_service.sheets_service, "get_worksheet", return_value=self.worksheet),
            mock.patch.object(user_service.sheets_service, "with_backoff",
                              side_effect=lambda fn, *a, **kw: fn(*a, **kw)),
            mock.patch.object(user_service, "reset_cache"),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def _ranges(self):
        return {u["range"]: u["values"][0][0] for u in self.worksheet.batch_update.call_args.args[0]}

    def test_writes_fullname_to_column_c_of_the_matching_row(self):
        self.assertTrue(user_service.update_profile("op111", fullName="ด.ต.สมชาย ใจดี"))
        self.assertEqual(self._ranges(), {"C2": "ด.ต.สมชาย ใจดี"})

    def test_phone_lands_in_its_own_column_not_next_to_the_name(self):
        """FullName คือ C, เบอร์โทร คือ J เขียนเป็นช่วงเดียวจะทับ D-I ทิ้ง"""
        self.assertTrue(user_service.update_profile("op111", fullName="ก", phone="0800000000"))
        self.assertEqual(self._ranges(), {"C2": "ก", "J2": "0800000000"})

    def test_a_field_left_out_is_not_touched(self):
        """ไม่ส่ง phone มา ต้องไม่เขียนทับเบอร์เดิมด้วยค่าว่าง"""
        user_service.update_profile("op111", fullName="ก")
        self.assertNotIn("J2", self._ranges())

    def test_the_row_is_matched_by_username_not_by_position(self):
        user_service.update_profile("st11", fullName="เปลี่ยนแถวที่สาม")
        self.assertEqual(self._ranges(), {"C3": "เปลี่ยนแถวที่สาม"})

    def test_username_is_matched_case_insensitively(self):
        self.assertTrue(user_service.update_profile("OP111", fullName="ก"))

    def test_unknown_username_writes_nothing(self):
        self.assertFalse(user_service.update_profile("ไม่มีคนนี้", fullName="ก"))
        self.worksheet.batch_update.assert_not_called()

    def test_a_call_with_nothing_to_change_writes_nothing(self):
        self.assertFalse(user_service.update_profile("op111"))
        self.worksheet.batch_update.assert_not_called()

    def test_password_role_and_station_are_not_reachable_from_here(self):
        """คอลัมน์ที่เปลี่ยนสิทธิ์หรือทำให้ล็อกอินไม่ได้ ต้องไม่อยู่ในรายการที่แก้ได้"""
        for column in ("Password", "Role", "Station_ID", "AccountType"):
            self.assertNotIn(column, user_service.EDITABLE_COLUMNS)


if __name__ == "__main__":
    unittest.main()
