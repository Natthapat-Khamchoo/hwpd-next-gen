"""
Tests for reading the tb_Users directory (unittest runner compatible).
No network — the sheet read is stubbed.
"""

import unittest
from unittest import mock

from app.services import user_service
from app.services.user_service import UserDirectoryUnavailable

HEADER = [
    "Username", "Password", "FullName", "Station_ID", "Unit_ID", "Role",
    "สถานะไปช่วยราชการ", "สถานะมาช่วยราชการ", "หมายเหตุ", "เบอร์โทร", "รหัส",
]

ROWS = [
    HEADER,
    ["test6", "1234", "พี่บุช", "51", "บก.", "Unit_Staff", "", "", "", "0824195636", "510"],
    # แถวสั้นกว่าหัวคอลัมน์ เกิดขึ้นจริงเมื่อช่องท้าย ๆ ว่าง
    ["test", "sha256$abc", "ปลื้ม", "50", "กองกำกับ", "Super_Commander"],
    ["", "ignored", "แถวว่าง", "11", "", "Unit_Staff"],
]


def with_rows(rows):
    return mock.patch.object(user_service.sheets_service, "read_table", return_value=rows)


class TestUserDirectory(unittest.TestCase):
    def setUp(self):
        user_service.reset_cache()
        self.addCleanup(user_service.reset_cache)

    def test_parses_users_keyed_by_lowercase_username(self):
        with with_rows(ROWS):
            users = user_service.get_all_users(force=True)

        self.assertEqual(sorted(users), ["test", "test6"])
        self.assertEqual(users["test6"]["fullName"], "พี่บุช")
        self.assertEqual(users["test6"]["station"], "51")
        self.assertEqual(users["test6"]["phone"], "0824195636")
        self.assertEqual(users["test6"]["role"], "Unit_Staff")

    def test_short_rows_do_not_crash_and_fill_blanks(self):
        with with_rows(ROWS):
            users = user_service.get_all_users(force=True)

        self.assertEqual(users["test"]["password"], "sha256$abc")
        self.assertEqual(users["test"]["phone"], "")
        self.assertEqual(users["test"]["code"], "")

    def test_rows_without_a_username_are_skipped(self):
        with with_rows(ROWS):
            users = user_service.get_all_users(force=True)
        self.assertNotIn("", users)

    def test_lookup_is_case_insensitive(self):
        with with_rows(ROWS):
            user_service.get_all_users(force=True)
            self.assertIsNotNone(user_service.get_user("TEST6"))
            self.assertIsNotNone(user_service.get_user(" test6 "))
            self.assertIsNone(user_service.get_user("nobody"))

    def test_missing_required_columns_is_reported(self):
        with with_rows([["Username", "FullName"], ["test6", "พี่บุช"]]):
            with self.assertRaises(UserDirectoryUnavailable) as ctx:
                user_service.get_all_users(force=True)
        self.assertIn("Password", str(ctx.exception))

    def test_empty_sheet_is_reported(self):
        with with_rows([]):
            with self.assertRaises(UserDirectoryUnavailable):
                user_service.get_all_users(force=True)

    def test_sheet_errors_surface_as_directory_unavailable(self):
        error = user_service.sheets_service.SheetWriteError("Google ปฏิเสธ")
        with mock.patch.object(user_service.sheets_service, "read_table", side_effect=error):
            with self.assertRaises(UserDirectoryUnavailable):
                user_service.get_all_users(force=True)

    def test_results_are_cached_until_reset(self):
        with with_rows(ROWS) as stub:
            user_service.get_all_users(force=True)
            user_service.get_all_users()
            user_service.get_all_users()
            self.assertEqual(stub.call_count, 1)

            user_service.reset_cache()
            user_service.get_all_users()
            self.assertEqual(stub.call_count, 2)


if __name__ == "__main__":
    unittest.main()
