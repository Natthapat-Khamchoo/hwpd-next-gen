"""
Tests for the reference/dropdown endpoints and change-password.
No network — the sheet reads and writes are stubbed.
"""

import unittest
from unittest import mock

from app.core.config import get_station_data
from app.services import reference_service, user_service

USER_HEADER = [
    "Username", "Password", "FullName", "Station_ID", "Unit_ID", "Role",
    "สถานะไปช่วยราชการ", "สถานะมาช่วยราชการ", "หมายเหตุ", "เบอร์โทร", "รหัส", "AccountType",
]

USER_ROWS = [
    USER_HEADER,
    ["st51", "sha256$aaa", "ร.ต.อ. ก", "51", "คลองขลุง", "Station_Admin", "", "", "", "0811111111", "", ""],
    ["st52", "sha256$bbb", "ด.ต. ข", "52", "เถิน", "Station_Admin", "", "", "", "0822222222", "", ""],
    ["fo5", "sha256$ccc", "พ.ต.ท. ค", "50", "ฝอ.กก.5", "Division_Admin", "", "", "", "0833333333", "", ""],
    ["st11", "sha256$ddd", "ร.ต.ท. ง", "11", "วังน้อย", "Station_Admin", "", "", "", "0844444444", "", ""],
]

# บัญชีประจำหน่วย — FullName เป็นชื่อสถานี ไม่ใช่ชื่อคน
UNIT_ROWS = USER_ROWS + [
    ["unit51", "sha256$eee", "ส.ทล.1 กก.5 บก.ทล.", "51", "คลองขลุง", "Station_Admin",
     "", "", "", "", "", "Unit"],
    ["unit50", "sha256$fff", "ฝอ.กก.5 บก.ทล.", "50", "ฝอ.กก.5", "Division_Admin",
     "", "", "", "", "", "unit"],   # ตัวพิมพ์เล็กก็ต้องนับ
]

CHARGE_ROWS = [
    ["ชื่อข้อหา", "crimeGroup", "reportTags", "sixteenBase", "isActive"],
    ["ขับรถเร็วเกินกว่าที่กฎหมายกำหนด", "", "", "", ""],
    ["ข้อหาที่เลิกใช้แล้ว", "", "", "", "FALSE"],
    ["ไม่มีใบอนุญาตขับขี่", "", "", "", "TRUE"],
    ["", "", "", "", ""],
]


def with_users(rows=USER_ROWS):
    return mock.patch.object(user_service.sheets_service, "read_table", return_value=rows)


class TestUserDropdowns(unittest.TestCase):
    def setUp(self):
        user_service.reset_cache()
        self.addCleanup(user_service.reset_cache)

    def test_station_sees_only_its_own_officers(self):
        with with_users():
            self.assertEqual(user_service.list_names_for_station("51"), ["ร.ต.อ. ก"])

    def test_division_hq_sees_every_station_in_its_division(self):
        with with_users():
            names = user_service.list_names_for_station("50")
        self.assertEqual(names, ["ด.ต. ข", "พ.ต.ท. ค", "ร.ต.อ. ก"])
        self.assertNotIn("ร.ต.ท. ง", names)  # กก.1 ต้องไม่หลุดมา

    def test_central_sees_everyone(self):
        with with_users():
            self.assertEqual(len(user_service.list_names_for_station("00")), 4)

    def test_names_are_sorted_so_the_dropdown_does_not_reshuffle(self):
        with with_users():
            first = user_service.list_names_for_station("00")
            user_service.reset_cache()
            second = user_service.list_names_for_station("00")
        self.assertEqual(first, second)
        self.assertEqual(first, sorted(first))

    def test_phone_map_keeps_the_leading_zero(self):
        with with_users():
            phones = user_service.phone_map_for_station("51")
        self.assertEqual(phones, {"ร.ต.อ. ก": "0811111111"})

    def test_phone_map_is_scoped_the_same_way_as_names(self):
        with with_users():
            self.assertNotIn("ร.ต.ท. ง", user_service.phone_map_for_station("50"))


class TestUnitAccountsAreNotOfficers(unittest.TestCase):
    """
    บัญชีประจำหน่วยใช้ชื่อสถานีเป็น FullName ถ้าไม่กรองออก ช่อง "ผู้รายงาน" จะมี
    "ส.ทล.1 กก.5 บก.ทล." ปนอยู่กับชื่อเจ้าหน้าที่ ซึ่งชวนกดผิด
    """

    def setUp(self):
        user_service.reset_cache()
        self.addCleanup(user_service.reset_cache)

    def test_flagged_accounts_are_recognised_regardless_of_case(self):
        with with_users(UNIT_ROWS):
            users = user_service.get_all_users(force=True)
        self.assertTrue(user_service.is_unit_account(users["unit51"]))
        self.assertTrue(user_service.is_unit_account(users["unit50"]))
        self.assertFalse(user_service.is_unit_account(users["st51"]))

    def test_they_are_left_out_of_the_officer_dropdown(self):
        with with_users(UNIT_ROWS):
            names = user_service.list_names_for_station("50")
        self.assertNotIn("ส.ทล.1 กก.5 บก.ทล.", names)
        self.assertNotIn("ฝอ.กก.5 บก.ทล.", names)
        self.assertIn("ร.ต.อ. ก", names)

    def test_they_are_left_out_of_the_phone_map(self):
        with with_users(UNIT_ROWS):
            phones = user_service.phone_map_for_station("50")
        self.assertNotIn("ส.ทล.1 กก.5 บก.ทล.", phones)

    def test_they_can_still_be_looked_up_and_logged_in(self):
        with with_users(UNIT_ROWS):
            account = user_service.get_user("unit51")
        self.assertIsNotNone(account)
        self.assertEqual(account["password"], "sha256$eee")

    def test_a_sheet_without_the_column_treats_everyone_as_a_person(self):
        # ชีตที่ยังไม่ได้เพิ่มคอลัมน์ต้องไม่ทำให้ dropdown ว่างเปล่า
        legacy_header = [c for c in USER_HEADER if c != "AccountType"]
        legacy = [legacy_header] + [row[:-1] for row in USER_ROWS[1:]]
        with with_users(legacy):
            names = user_service.list_names_for_station("50")
        self.assertEqual(names, ["ด.ต. ข", "พ.ต.ท. ค", "ร.ต.อ. ก"])


class TestUnitDropdown(unittest.TestCase):
    def test_units_come_from_station_config(self):
        self.assertEqual(get_station_data("51")["units"][0], "คลองขลุง")
        self.assertIn("แม่สอด", get_station_data("51")["units"])

    def test_every_configured_station_has_at_least_one_unit(self):
        for division in range(1, 9):
            for number in range(1, 7):
                units = get_station_data(f"{division}{number}")["units"]
                self.assertTrue(units, f"สถานี {division}{number} ไม่มีหน่วยบริการ")


class TestChargeDropdown(unittest.TestCase):
    def setUp(self):
        reference_service.reset_cache()
        self.addCleanup(reference_service.reset_cache)

    def test_inactive_and_blank_rows_are_dropped(self):
        with mock.patch.object(reference_service.sheets_service, "read_table", return_value=CHARGE_ROWS):
            charges = reference_service.get_charges(force=True)
        self.assertEqual(charges, ["ขับรถเร็วเกินกว่าที่กฎหมายกำหนด", "ไม่มีใบอนุญาตขับขี่"])

    def test_results_are_cached_until_reset(self):
        with mock.patch.object(
            reference_service.sheets_service, "read_table", return_value=CHARGE_ROWS
        ) as stub:
            reference_service.get_charges(force=True)
            reference_service.get_charges()
            self.assertEqual(stub.call_count, 1)

    def test_sheet_errors_surface_as_reference_unavailable(self):
        error = reference_service.sheets_service.SheetWriteError("Google ปฏิเสธ")
        with mock.patch.object(reference_service.sheets_service, "read_table", side_effect=error):
            with self.assertRaises(reference_service.ReferenceDataUnavailable):
                reference_service.get_charges(force=True)


class TestUpdatePassword(unittest.TestCase):
    def setUp(self):
        user_service.reset_cache()
        self.addCleanup(user_service.reset_cache)

    def test_writes_to_the_password_cell_of_the_matching_row(self):
        worksheet = mock.Mock()
        with with_users(), mock.patch.object(
            user_service.sheets_service, "get_worksheet", return_value=worksheet
        ), mock.patch.object(
            user_service.sheets_service, "with_backoff", side_effect=lambda fn, *a, **kw: fn(*a, **kw)
        ):
            self.assertTrue(user_service.update_password("st52", "sha256$new"))

        # st52 อยู่แถวที่ 3 ของชีต (หัวคอลัมน์คือแถว 1) และ Password คือคอลัมน์ B
        worksheet.update.assert_called_once()
        self.assertEqual(worksheet.update.call_args.kwargs["range_name"], "B3")
        self.assertEqual(worksheet.update.call_args.kwargs["values"], [["sha256$new"]])

    def test_unknown_username_writes_nothing(self):
        worksheet = mock.Mock()
        with with_users(), mock.patch.object(
            user_service.sheets_service, "get_worksheet", return_value=worksheet
        ):
            self.assertFalse(user_service.update_password("nobody", "sha256$new"))
        worksheet.update.assert_not_called()

    def test_lookup_is_case_insensitive(self):
        worksheet = mock.Mock()
        with with_users(), mock.patch.object(
            user_service.sheets_service, "get_worksheet", return_value=worksheet
        ), mock.patch.object(
            user_service.sheets_service, "with_backoff", side_effect=lambda fn, *a, **kw: fn(*a, **kw)
        ):
            self.assertTrue(user_service.update_password("ST51", "sha256$new"))
        self.assertEqual(worksheet.update.call_args.kwargs["range_name"], "B2")


if __name__ == "__main__":
    unittest.main()
