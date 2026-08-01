"""
Tests for the read side: pending queues, missions, and status changes.
No network — the sheet reads and writes are stubbed.
"""

import unittest
from contextlib import contextmanager
from unittest import mock

from app.core.schema import get_columns
from app.services import query_service
from app.services.query_service import (
    COL_ACTION_BY,
    COL_ACTUAL_DATE,
    COL_IS_ACTIVE,
    COL_RECORD_ID,
    COL_STATION_ID,
    COL_STATUS,
    COL_TIMESTAMP,
    RecordNotFound,
)

DB_ID = "sheet-for-division-5"


def row(table, **values):
    """สร้างแถวดิบตามลำดับคอลัมน์จริงของตาราง โดยระบุเฉพาะช่องที่สนใจ"""
    return [values.get(column, "") for column in get_columns(table)]


RESULT_ROWS = [
    get_columns("tb_DailyResult"),
    row("tb_DailyResult", **{
        COL_RECORD_ID: "RST-1", COL_TIMESTAMP: "2026-07-27T08:00:00", COL_ACTION_BY: "st51",
        COL_STATUS: "Pending", COL_IS_ACTIVE: "TRUE", COL_STATION_ID: "51",
        "Data_UnitID": "คลองขลุง", "ยอด ว.43": "12", "ยอด บริการ": "5", "ยอด ว.20": "3",
    }),
    row("tb_DailyResult", **{
        COL_RECORD_ID: "RST-2", COL_TIMESTAMP: "2026-07-27T06:00:00", COL_ACTION_BY: "st52",
        COL_STATUS: "Pending", COL_IS_ACTIVE: "TRUE", COL_STATION_ID: "52",
        "ยอด ว.43": "7", "ยอด ว.42": "2", "ยอด ว.20": "1",
    }),
    row("tb_DailyResult", **{
        COL_RECORD_ID: "RST-3", COL_TIMESTAMP: "2026-07-26T08:00:00", COL_ACTION_BY: "st51",
        COL_STATUS: "Approved", COL_IS_ACTIVE: "TRUE", COL_STATION_ID: "51",
        "ยอด ว.43": "100", "ยอด ว.42": "9", "ยอด ว.20": "4",
    }),
    row("tb_DailyResult", **{
        COL_RECORD_ID: "RST-4", COL_TIMESTAMP: "2026-07-26T09:00:00", COL_ACTION_BY: "st51",
        COL_STATUS: "Canceled", COL_IS_ACTIVE: "FALSE", COL_STATION_ID: "51",
        "ยอด ว.43": "999",
    }),
]

MISSION_ROWS = [
    get_columns("tb_Missions"),
    row("tb_Missions", **{
        COL_RECORD_ID: "MIS-1", COL_IS_ACTIVE: "TRUE", COL_STATION_ID: "51",
        COL_ACTUAL_DATE: "2026-07-27", "วันที่เวลาเริ่มภารกิจ": "2026-07-27T09:00",
        "หน่วยบริการที่เกี่ยวข้อง - เก็บเป็นข้อความคั่นด้วยลูกน้ำ": "คลองขลุง, นครชุม",
        "รายละเอียดภารกิจ": "คุ้มกันขบวน", "สถานที่": "ทล.1",
    }),
    row("tb_Missions", **{
        COL_RECORD_ID: "MIS-2", COL_IS_ACTIVE: "TRUE", COL_STATION_ID: "51",
        COL_ACTUAL_DATE: "2026-07-20", "วันที่เวลาเริ่มภารกิจ": "2026-07-20T09:00",
        "หน่วยบริการที่เกี่ยวข้อง - เก็บเป็นข้อความคั่นด้วยลูกน้ำ": "แม่สอด",
        "รายละเอียดภารกิจ": "นอกช่วงวันที่",
    }),
    row("tb_Missions", **{
        COL_RECORD_ID: "MIS-3", COL_IS_ACTIVE: "FALSE", COL_STATION_ID: "51",
        COL_ACTUAL_DATE: "2026-07-27", "รายละเอียดภารกิจ": "ยกเลิกแล้ว",
    }),
]


@contextmanager
def stub_sheets(tables):
    """
    แทน read_table ด้วยข้อมูลจำลอง ตารางที่ไม่ได้ระบุถือว่ายังไม่มีแท็บ

    ล้างแคชระดับตารางทั้งก่อนและหลัง เพราะ query_service เก็บผลไว้ 30 วินาที
    เทสที่วางข้อมูลจำลองชุดใหม่ต้องไม่เห็นของที่เทสก่อนหน้าอ่านค้างไว้
    """
    def fake(spreadsheet_id, table_name):
        if table_name in tables:
            return tables[table_name]
        raise query_service.sheets_service.SheetWriteError(f"ไม่พบตาราง {table_name} ในสเปรดชีต")

    query_service.invalidate_cache()
    # yield ตัว mock ออกไปด้วย เทสที่นับจำนวนการอ่านใช้ `as stub` แล้วดู call_count
    with mock.patch.object(query_service.sheets_service, "read_table", side_effect=fake) as stub:
        yield stub
    query_service.invalidate_cache()


def stub_router():
    return mock.patch.object(query_service, "get_target_db_id", return_value=DB_ID)


class TestReadRows(unittest.TestCase):
    def test_maps_cells_onto_schema_column_names(self):
        with stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            rows = query_service.read_rows(DB_ID, "tb_DailyResult")
        self.assertEqual(rows[0][COL_RECORD_ID], "RST-1")
        self.assertEqual(rows[0]["ยอด ว.43"], "12")
        self.assertEqual(rows[0]["_row"], 2)

    def test_missing_tab_reads_as_empty_not_an_error(self):
        with stub_sheets({}):
            self.assertEqual(query_service.read_rows(DB_ID, "tb_Arrests"), [])

    def test_other_sheet_errors_still_raise(self):
        error = query_service.sheets_service.SheetWriteError("Google ปฏิเสธ")
        with mock.patch.object(query_service.sheets_service, "read_table", side_effect=error):
            with self.assertRaises(query_service.sheets_service.SheetWriteError):
                query_service.read_rows(DB_ID, "tb_DailyResult")


class TestIsActive(unittest.TestCase):
    def test_accepts_the_spellings_both_writers_produce(self):
        for value in ("TRUE", "true", "True", True):
            self.assertTrue(query_service.is_active(value))
        for value in ("FALSE", "false", "", None, 0):
            self.assertFalse(query_service.is_active(value))


class TestPendingQueues(unittest.TestCase):
    def test_station_sees_only_its_own_pending_rows(self):
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            items = query_service.pending_for_station("51", query_service.GENERAL_TABLES)
        self.assertEqual([i["recordId"] for i in items], ["RST-1"])

    def test_division_hq_sees_every_station_in_its_division(self):
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            items = query_service.pending_for_station("50", query_service.GENERAL_TABLES)
        self.assertEqual(sorted(i["recordId"] for i in items), ["RST-1", "RST-2"])

    def test_queue_is_oldest_first(self):
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            items = query_service.pending_for_station("50", query_service.GENERAL_TABLES)
        self.assertEqual([i["recordId"] for i in items], ["RST-2", "RST-1"])

    def test_approved_and_canceled_rows_stay_out_of_the_queue(self):
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            ids = [i["recordId"] for i in query_service.pending_for_station("50", query_service.GENERAL_TABLES)]
        self.assertNotIn("RST-3", ids)
        self.assertNotIn("RST-4", ids)

    def test_reporter_shows_the_real_name_when_known(self):
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            items = query_service.pending_for_station("51", query_service.GENERAL_TABLES, {"st51": "ร.ต.อ. ก"})
        self.assertEqual(items[0]["reporter"], "ร.ต.อ. ก")

    def test_reporter_falls_back_to_the_account_name(self):
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            items = query_service.pending_for_station("51", query_service.GENERAL_TABLES, {})
        self.assertEqual(items[0]["reporter"], "st51")

    def test_summary_line_reads_the_right_columns(self):
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            items = query_service.pending_for_station("51", query_service.GENERAL_TABLES)
        self.assertEqual(items[0]["details"], "ว.43 = 12, บริการ = 5, ว.20 = 3")

    def test_timestamp_is_formatted_for_display(self):
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            items = query_service.pending_for_station("51", query_service.GENERAL_TABLES)
        self.assertEqual(items[0]["timestamp"], "27/07/2026 08:00")

    def test_my_pending_is_scoped_to_one_account_and_newest_first(self):
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            items = query_service.pending_for_user("50", "st51")
        self.assertEqual([i["recordId"] for i in items], ["RST-1"])


class TestSummaryColumnNames(unittest.TestCase):
    """
    _summarize อ่านค่าด้วย .get() ชื่อคอลัมน์ที่พิมพ์ผิดจะคืนสตริงว่างเงียบ ๆ
    ไม่ใช่ error เทสนี้จึงตรวจว่าทุกชื่อที่อ้างถึงมีจริงใน schema
    """

    EXPECTED = {
        "tb_DailyResult": ["ยอด ว.43", "ยอด บริการ", "ยอด ว.20", "ยอด ว.42"],
        "tb_FuelOil": ["จำนวนลิตร", "ราคาบาท", "ประเภทน้ำมัน/รถ", "ทะเบียนรถ"],
        "tb_Arrests": ["ข้อหาทั้งหมด", "หัวข้อการจับกุม"],
        "tb_Accidents": ["ทล., กม., ตำบล, อำเภอ, จังหวัด"],
        "tb_RoyalGuard": ["ชื่อภารกิจ"],
        "tb_OtherDuties": ["การปฏิบัติ"],
        "tb_Missions": [
            "วันที่เวลาเริ่มภารกิจ",
            "วันที่เวลาสิ้นสุดภารกิจ",
            "หน่วยบริการที่เกี่ยวข้อง - เก็บเป็นข้อความคั่นด้วยลูกน้ำ",
            "รายละเอียดภารกิจ",
            "สถานที่",
        ],
    }

    def test_every_column_the_read_side_reads_exists(self):
        for table, columns in self.EXPECTED.items():
            available = get_columns(table)
            for column in columns:
                self.assertIn(column, available, f"{table} ไม่มีคอลัมน์ {column}")

    def test_every_approvable_table_has_a_schema(self):
        for table in query_service.APPROVABLE_TABLES:
            self.assertTrue(get_columns(table))


class TestMissions(unittest.TestCase):
    def test_filters_by_date_range(self):
        with stub_router(), stub_sheets({"tb_Missions": MISSION_ROWS}):
            found = query_service.missions_for_unit("51", "", "2026-07-25", "2026-07-31")
        self.assertEqual([m["recordId"] for m in found], ["MIS-1"])

    def test_blank_unit_returns_every_unit_of_the_station(self):
        with stub_router(), stub_sheets({"tb_Missions": MISSION_ROWS}):
            found = query_service.missions_for_unit("51", "", "", "")
        self.assertEqual([m["recordId"] for m in found], ["MIS-2", "MIS-1"])

    def test_unit_filter_matches_inside_the_comma_separated_list(self):
        with stub_router(), stub_sheets({"tb_Missions": MISSION_ROWS}):
            found = query_service.missions_for_unit("51", "นครชุม", "", "")
        self.assertEqual([m["recordId"] for m in found], ["MIS-1"])

    def test_canceled_missions_are_hidden(self):
        with stub_router(), stub_sheets({"tb_Missions": MISSION_ROWS}):
            ids = [m["recordId"] for m in query_service.missions_for_unit("51", "", "", "")]
        self.assertNotIn("MIS-3", ids)

    def test_returns_the_fields_the_form_renders(self):
        with stub_router(), stub_sheets({"tb_Missions": MISSION_ROWS}):
            mission = query_service.missions_for_unit("51", "", "2026-07-27", "2026-07-27")[0]
        for field in ("startTime", "targetUnits", "details", "location"):
            self.assertTrue(mission[field], f"ไม่มีค่าในฟิลด์ {field}")


class TestStationOverview(unittest.TestCase):
    def test_totals_count_approved_rows_and_skip_pending_and_canceled(self):
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            stats = query_service.station_overview("51")["stats"]
        # นับเฉพาะ RST-3 (Approved) — RST-1 ยัง Pending, RST-4 ถูกยกเลิก
        self.assertEqual(stats["v43"], 100)
        self.assertEqual(stats["v42"], 9)
        self.assertEqual(stats["v20"], 4)

    def test_queue_and_totals_agree_with_the_separate_queries(self):
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            overview = query_service.station_overview("50", {"st51": "ร.ต.อ. ก"})
            separate = query_service.pending_for_station(
                "50", query_service.GENERAL_TABLES, {"st51": "ร.ต.อ. ก"}
            )
        self.assertEqual(
            [i["recordId"] for i in overview["pending"]],
            [i["recordId"] for i in separate],
        )
        self.assertEqual(overview["stats"]["pendingCount"], len(separate))

    def test_reads_each_table_only_once(self):
        tables = {"tb_DailyResult": RESULT_ROWS}
        with stub_router(), stub_sheets(tables) as stub:
            query_service.station_overview("51")
        # 5 ตารางทั่วไป + 1 ตารางน้ำมัน ไม่ใช่ 16 ครั้งแบบที่แยกเป็นสามฟังก์ชัน
        self.assertEqual(stub.call_count, len(query_service.GENERAL_TABLES) + len(query_service.FUEL_TABLES))

    def test_fuel_rows_go_to_the_fuel_queue_not_the_general_one(self):
        fuel_rows = [
            get_columns("tb_FuelOil"),
            row("tb_FuelOil", **{
                COL_RECORD_ID: "FUEL-1", COL_TIMESTAMP: "2026-07-27T10:00:00",
                COL_STATUS: "Pending", COL_IS_ACTIVE: "TRUE", COL_STATION_ID: "51",
                "ทะเบียนรถ": "กท 5101", "จำนวนลิตร": "40.5", "ราคาบาท": "1200",
                "ประเภทน้ำมัน/รถ": "ดีเซล",
            }),
        ]
        with stub_router(), stub_sheets({"tb_FuelOil": fuel_rows}):
            overview = query_service.station_overview("51")
        self.assertEqual(overview["pending"], [])
        self.assertEqual(len(overview["fuel"]), 1)
        self.assertEqual(overview["fuel"][0]["plate"], "กท 5101")
        self.assertIn("40.5 ลิตร", overview["fuel"][0]["details"])

    def test_only_todays_approvals_are_counted(self):
        from datetime import datetime as real_datetime

        today = real_datetime.now().strftime("%Y-%m-%d")
        rows = [
            get_columns("tb_Arrests"),
            row("tb_Arrests", **{
                COL_RECORD_ID: "ARR-1", COL_STATUS: "Approved", COL_IS_ACTIVE: "TRUE",
                COL_STATION_ID: "51", "Sys_LastUpdate": f"{today}T10:00:00",
            }),
            row("tb_Arrests", **{
                COL_RECORD_ID: "ARR-2", COL_STATUS: "Approved", COL_IS_ACTIVE: "TRUE",
                COL_STATION_ID: "51", "Sys_LastUpdate": "2020-01-01T10:00:00",
            }),
        ]
        with stub_router(), stub_sheets({"tb_Arrests": rows}):
            stats = query_service.station_overview("51")["stats"]
        self.assertEqual(stats["approvedToday"], 1)
        self.assertEqual(stats["arrest"], 2)  # ยอดสะสมนับทั้งสองใบ


class TestStatusChanges(unittest.TestCase):
    def test_find_record_reports_a_missing_id(self):
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            with self.assertRaises(RecordNotFound):
                query_service.find_record("51", "tb_DailyResult", "ไม่มีอยู่จริง")

    def test_set_status_writes_the_status_and_active_cells_only(self):
        worksheet = mock.Mock()
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            record = query_service.find_record("51", "tb_DailyResult", "RST-1")

        with mock.patch.object(
            query_service.sheets_service, "get_worksheet", return_value=worksheet
        ), mock.patch.object(
            query_service.sheets_service, "with_backoff", side_effect=lambda fn, *a, **kw: fn(*a, **kw)
        ):
            query_service.set_status(record, "tb_DailyResult", query_service.STATUS_APPROVED, True)

        updates = worksheet.batch_update.call_args.args[0]
        ranges = {u["range"] for u in updates}
        self.assertEqual(ranges, {"C2", "E2:F2"})
        self.assertEqual(updates[1]["values"], [["Approved", True]])
        # คอลัมน์ D (Sys_ActionBy) ต้องไม่ถูกแตะ ไม่งั้นชื่อผู้ส่งจะถูกทับ
        self.assertNotIn("D2", ranges)

    def test_cancel_turns_the_active_flag_off(self):
        worksheet = mock.Mock()
        with stub_router(), stub_sheets({"tb_DailyResult": RESULT_ROWS}):
            record = query_service.find_record("51", "tb_DailyResult", "RST-1")

        with mock.patch.object(
            query_service.sheets_service, "get_worksheet", return_value=worksheet
        ), mock.patch.object(
            query_service.sheets_service, "with_backoff", side_effect=lambda fn, *a, **kw: fn(*a, **kw)
        ):
            query_service.set_status(record, "tb_DailyResult", query_service.STATUS_CANCELED, False)

        self.assertEqual(worksheet.batch_update.call_args.args[0][1]["values"], [["Canceled", False]])


class TestColumnLetter(unittest.TestCase):
    def test_maps_index_to_spreadsheet_column(self):
        for index, letter in [(0, "A"), (4, "E"), (25, "Z"), (26, "AA"), (33, "AH")]:
            self.assertEqual(query_service._column_letter(index), letter)

    def test_widest_table_still_lands_in_range(self):
        widest = max(len(get_columns(t)) for t in query_service.APPROVABLE_TABLES)
        self.assertTrue(query_service._column_letter(widest - 1).isalpha())


if __name__ == "__main__":
    unittest.main()
