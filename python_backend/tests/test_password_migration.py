"""
Tests for the plaintext-to-hash migration.
No network — the sheet read is stubbed.
"""

import importlib.util
import os
import sys
import unittest
from unittest import mock

from app.core.security import verify_password

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "scripts", "hash_plaintext_passwords.py")
_spec = importlib.util.spec_from_file_location("hash_plaintext_passwords", _PATH)
migration = importlib.util.module_from_spec(_spec)
sys.modules["hash_plaintext_passwords"] = migration
_spec.loader.exec_module(migration)

HEADER = ["Username", "Password", "FullName", "Station_ID", "Unit_ID", "Role"]

ROWS = [
    HEADER,
    ["test", "1234", "ปลื้ม", "50", "กองกำกับ", "Super_Commander"],
    ["st51", "sha256$already-hashed", "ส.ทล.1", "51", "คลองขลุง", "Station_Admin"],
    ["test6", "  spaced  ", "พี่บุช", "51", "บก.", "Unit_Staff"],
    ["", "1234", "แถวว่าง", "11", "", "Unit_Staff"],
    ["short-row"],
]


class TestCollect(unittest.TestCase):
    def test_only_plaintext_rows_are_picked_up(self):
        pending = migration.collect(ROWS)
        self.assertEqual([p["username"] for p in pending], ["test", "test6"])

    def test_already_hashed_rows_are_left_alone(self):
        self.assertNotIn("st51", [p["username"] for p in migration.collect(ROWS)])

    def test_rows_without_a_username_are_skipped(self):
        self.assertNotIn("", [p["username"] for p in migration.collect(ROWS)])

    def test_short_rows_do_not_crash(self):
        migration.collect(ROWS)   # ต้องไม่ขว้าง IndexError

    def test_target_cell_is_the_password_column_of_that_row(self):
        pending = {p["username"]: p for p in migration.collect(ROWS)}
        self.assertEqual(pending["test"]["cell"], "B2")
        self.assertEqual(pending["test6"]["cell"], "B4")

    def test_the_hash_still_verifies_the_original_password(self):
        pending = {p["username"]: p for p in migration.collect(ROWS)}
        self.assertTrue(verify_password("test", "1234", pending["test"]["hashed"]))
        # ค่าที่มีช่องว่างหน้าหลังถูก strip ก่อน hash รหัสที่ผู้ใช้พิมพ์จึงต้องเป็นค่าที่ strip แล้ว
        self.assertTrue(verify_password("test6", "spaced", pending["test6"]["hashed"]))

    def test_a_wrong_password_does_not_verify_against_the_new_hash(self):
        pending = {p["username"]: p for p in migration.collect(ROWS)}
        self.assertFalse(verify_password("test", "ผิด", pending["test"]["hashed"]))

    def test_running_twice_finds_nothing_the_second_time(self):
        pending = migration.collect(ROWS)
        migrated = [list(r) for r in ROWS]
        for item in pending:
            migrated[item["row"] - 1][1] = item["hashed"]
        self.assertEqual(migration.collect(migrated), [])

    def test_a_missing_password_column_stops_the_run(self):
        with self.assertRaises(SystemExit):
            migration.collect([["Username", "FullName"], ["test", "ปลื้ม"]])

    def test_a_hash_that_fails_its_own_check_aborts_before_any_write(self):
        with mock.patch.object(migration, "verify_password", return_value=False):
            with self.assertRaises(SystemExit) as ctx:
                migration.collect(ROWS)
        self.assertIn("หยุดทั้งรอบ", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
