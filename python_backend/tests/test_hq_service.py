"""
เทสของหน้า ฝอ.กก. และหน้าผู้กำกับการ

จุดที่ทดสอบเน้นตรงที่พอร์ตมาแล้วพลาดง่าย — การนับกำลังพลไปช่วย/มาช่วยข้ามสถานี
การแยกยอดน้ำมันกับน้ำมันเครื่องออกจากกัน และการอ่านวันที่ที่ชีตเก็บไว้หลายรูปแบบ
"""

import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest import mock

from app.services import hq_service, query_service

DB_ID = "db-test"


def _future(days: int) -> str:
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


@contextmanager
def stub_sheets(tables):
    """เหมือน stub_sheets ของ test_query_service — hq_service อ่านผ่าน query_service ทั้งหมด"""
    def fake(spreadsheet_id, table_name):
        if table_name in tables:
            return tables[table_name]
        raise query_service.sheets_service.SheetWriteError(f"ไม่พบตาราง {table_name} ในสเปรดชีต")

    query_service.invalidate_cache()
    with mock.patch.object(query_service.sheets_service, "read_table", side_effect=fake) as stub:
        with mock.patch.object(hq_service, "get_target_db_id", return_value=DB_ID):
            yield stub
    query_service.invalidate_cache()


def users_table(rows):
    header = [
        "Username", "Password", "FullName", "Station_ID", "Unit_ID", "Role",
        "สถานะไปช่วยราชการ", "สถานะมาช่วยราชการ", "หมายเหตุ", "เบอร์โทร", "รหัส",
        "วันที่เริ่มช่วยราชการ", "วันที่สิ้นสุดช่วยราชการ", "AccountType",
    ]
    return [header] + rows


def user_row(username, name, station, help_station="", start="", end=""):
    return [username, "x", name, station, "หน่วย", "Unit_Staff", help_station, "", "", "", "", start, end, "unit"]


class TestDatePart(unittest.TestCase):
    def test_reads_the_three_shapes_the_sheet_actually_stores(self):
        self.assertEqual(hq_service._date_part("2026-07-31"), "2026-07-31")
        self.assertEqual(hq_service._date_part("2026-07-31T08:30:00"), "2026-07-31")
        self.assertEqual(hq_service._date_part("31/07/2026 08:30"), "2026-07-31")

    def test_unparseable_values_are_excluded_not_defaulted_to_today(self):
        # คืนสตริงว่างแล้วให้ _in_range ตัดทิ้ง ถ้าเดาเป็นวันนี้ แถวขยะจะโผล่ในทุกช่วงวันที่
        self.assertEqual(hq_service._date_part("ไม่ระบุ"), "")
        self.assertFalse(hq_service._in_range("ไม่ระบุ", "2026-07-01", "2026-07-31"))


class TestHelpAssignment(unittest.TestCase):
    def test_no_dates_means_still_in_effect(self):
        self.assertTrue(hq_service._help_active("52", "", ""))

    def test_expired_assignment_is_not_counted(self):
        self.assertFalse(hq_service._help_active("52", _future(-30), _future(-10)))

    def test_future_assignment_is_not_counted_yet(self):
        self.assertFalse(hq_service._help_active("52", _future(10), _future(20)))

    def test_blank_station_is_never_active_even_with_dates(self):
        self.assertFalse(hq_service._help_active("", _future(-1), _future(1)))


class TestRankGroup(unittest.TestCase):
    def test_deputy_is_checked_before_inspector(self):
        # "รอง สว." มีคำว่า "สว." อยู่ในตัว สลับลำดับเมื่อไหร่ทุกคนจะถูกดันขึ้นแถวบน
        self.assertEqual(hq_service._rank_group("พ.ต.ท. ก รอง สว.กก.5"), "level2")
        self.assertEqual(hq_service._rank_group("พ.ต.ท. ข สว.กก.5"), "level1")
        self.assertEqual(hq_service._rank_group("ด.ต. ค"), "level3")


class TestManpowerOverview(unittest.TestCase):
    def test_transfer_moves_the_head_count_between_stations(self):
        rows = users_table([
            user_row("a", "ด.ต. เอ", "51"),
            user_row("b", "ด.ต. บี", "51", help_station="52"),
            user_row("c", "ด.ต. ซี", "52"),
        ])
        with stub_sheets({"tb_Users": rows}):
            with mock.patch.object(hq_service, "get_division_stations", return_value=["50", "51", "52"]):
                summary = hq_service.manpower_overview("50")

        self.assertEqual((summary["51"]["base"], summary["51"]["out"], summary["51"]["net"]), (2, 1, 1))
        self.assertEqual((summary["52"]["base"], summary["52"]["in"], summary["52"]["net"]), (1, 1, 2))
        # ยอดรวมทั้ง กก. ต้องไม่เปลี่ยน คนย้ายภายในกองไม่ได้เพิ่มหรือลดกำลังพล
        self.assertEqual(summary["total"]["net"], 3)

    def test_help_from_another_division_adds_without_a_matching_base(self):
        rows = users_table([
            user_row("a", "ด.ต. เอ", "51"),
            user_row("x", "ด.ต. เอ็กซ์", "31", help_station="51"),
        ])
        with stub_sheets({"tb_Users": rows}):
            with mock.patch.object(hq_service, "get_division_stations", return_value=["50", "51"]):
                summary = hq_service.manpower_overview("50")

        self.assertEqual(summary["51"]["base"], 1)
        self.assertEqual(summary["51"]["in"], 1)
        self.assertEqual(summary["51"]["net"], 2)


class TestManpowerData(unittest.TestCase):
    def test_incoming_officer_is_listed_separately_and_not_in_the_base(self):
        rows = users_table([
            user_row("a", "ด.ต. เอ", "51"),
            user_row("x", "ด.ต. เอ็กซ์", "52", help_station="51"),
        ])
        with stub_sheets({"tb_Users": rows}):
            data = hq_service.manpower_data("51")

        self.assertEqual(data["stats"]["base"], 1)
        self.assertEqual(data["stats"]["in"], 1)
        self.assertEqual(data["stats"]["net"], 2)
        self.assertEqual([p["username"] for p in data["chart"]["incoming"]], ["x"])

    def test_rows_without_a_name_are_skipped(self):
        rows = users_table([user_row("a", "", "51"), user_row("b", "ด.ต. บี", "51")])
        with stub_sheets({"tb_Users": rows}):
            data = hq_service.manpower_data("51")
        self.assertEqual(data["stats"]["base"], 1)


class TestFuelSummary(unittest.TestCase):
    def _tables(self):
        quota = [
            ["MonthYear", "StationID", "QuotaLiters", "QuotaBaht", "LastUpdate", "ActionBy", "QuotaOilLiters"],
            ["'2026-07", "51", "0", "5000", "", "fo5", "40"],
        ]
        oil_header = [
            "Sys_RecordID", "Sys_Timestamp", "Sys_LastUpdate", "Sys_ActionBy", "Sys_Status", "Sys_IsActive",
            "Data_ActualDate", "Data_StationID", "Data_UnitID", "ประเภทรายการ", "วันเวลาที่ทำรายการ",
            "ผู้ดำเนินการ", "ทะเบียนรถ", "เลขไมล์ปัจจุบัน", "จำนวนลิตร", "ประเภทน้ำมัน/รถ", "ราคาบาท",
            "เลขที่ใบเสร็จ", "เลขไมล์ครั้งก่อน", "ระยะทางใช้งาน(กม.)",
        ]
        oil = [
            oil_header,
            ["F-1", "2026-07-05 09:00", "", "st51", "Approved", "TRUE", "2026-07-05", "51", "หน่วย",
             "เติมน้ำมัน", "2026-07-05", "st51", "กท-1", "1000", "40", "ดีเซล", "1600", "R-1", "900", "100"],
            ["F-2", "2026-07-06 09:00", "", "st51", "Approved", "TRUE", "2026-07-06", "51", "หน่วย",
             "เปลี่ยนน้ำมันเครื่อง", "2026-07-06", "st51", "กท-1", "1100", "5", "เครื่อง", "800", "R-2", "1000", "100"],
            # เดือนอื่น ต้องไม่ถูกนับ
            ["F-3", "2026-06-01 09:00", "", "st51", "Approved", "TRUE", "2026-06-01", "51", "หน่วย",
             "เติมน้ำมัน", "2026-06-01", "st51", "กท-1", "800", "99", "ดีเซล", "9999", "R-3", "700", "100"],
        ]
        return {"tb_FuelQuota": quota, "tb_FuelOil": oil, "tb_Users": users_table([])}

    def test_fuel_and_engine_oil_are_counted_in_separate_buckets(self):
        with stub_sheets(self._tables()):
            with mock.patch.object(hq_service, "get_division_stations", return_value=["50", "51"]):
                result = hq_service.fuel_summary("50", "2026-07")

        station = result["summary"]["51"]
        self.assertEqual(station["usedB"], 1600)
        self.assertEqual(station["usedL"], 40)
        # น้ำมันเครื่องไม่ควรบวกเข้ายอดบาทของน้ำมันรถ ของเดิมแยกสองช่องไว้ตั้งแต่ต้น
        self.assertEqual(station["oilUsedL"], 5)
        self.assertEqual(station["quotaB"], 5000)
        self.assertEqual(station["oilQuotaL"], 40)

    def test_other_months_are_excluded(self):
        with stub_sheets(self._tables()):
            with mock.patch.object(hq_service, "get_division_stations", return_value=["50", "51"]):
                result = hq_service.fuel_summary("50", "2026-07")
        self.assertEqual(len(result["logs"]), 2)
        self.assertEqual(result["summary"]["total"]["usedB"], 1600)


class TestMissionCalendar(unittest.TestCase):
    def _missions(self, station_value):
        header = [
            "Sys_RecordID", "Sys_Timestamp", "Sys_LastUpdate", "Sys_ActionBy", "Sys_Status", "Sys_IsActive",
            "Data_ActualDate", "Data_StationID", "Data_UnitID", "วันที่เวลาที่แจ้ง", "วันที่เวลาเริ่มภารกิจ",
            "วันที่เวลาสิ้นสุดภารกิจ", "หน่วยบริการที่เกี่ยวข้อง - เก็บเป็นข้อความคั่นด้วยลูกน้ำ",
            "รายละเอียดภารกิจ", "สถานที่", "Attachment_Folde",
        ]
        return [header, [
            "M-1", "2026-07-01", "", "fo5", "Active", "TRUE", "2026-07-10", station_value, "หน่วย",
            "2026-07-01", "2026-07-10T08:00:00", "2026-07-10T16:00:00", "", "ตรวจจุด", "ทล.1",
        ]]

    def test_station_written_as_a_display_name_is_normalised(self):
        # ตารางภารกิจกรอกรหัสสถานีมาหลายแบบ ถ้าไม่ปรับ ปฏิทินจะจัดไปอยู่ผิดสถานี
        for written in ("51", "ส.ทล.1", "1"):
            with stub_sheets({"tb_Missions": self._missions(written)}):
                with mock.patch.object(hq_service, "get_division_stations", return_value=["50", "51"]):
                    result = hq_service.mission_calendar("50", "2026-07")
            self.assertEqual(result[0]["stationId"], "51", f"กรอกมาเป็น {written}")

    def test_station_outside_the_division_falls_back_to_headquarters(self):
        with stub_sheets({"tb_Missions": self._missions("99")}):
            with mock.patch.object(hq_service, "get_division_stations", return_value=["50", "51"]):
                result = hq_service.mission_calendar("50", "2026-07")
        self.assertEqual(result[0]["stationId"], "00")


if __name__ == "__main__":
    unittest.main()
