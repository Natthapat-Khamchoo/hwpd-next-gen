"""
Guards that each prepare_* row lines up with the sheet columns it is written into.
A drift here writes values into the wrong columns without any error.
"""

import unittest
from unittest import mock

from app.core.schema import NON_STANDARD_TABLES, SYSTEM_COLUMNS, TABLE_COLUMNS, get_columns
from app.services.report_service import (
    prepare_accident_report,
    prepare_arrest_report,
    prepare_checkpoint_report,
    prepare_daily_report,
    prepare_daily_result,
    prepare_document_record,
    prepare_fuel_record,
    prepare_mission_report,
    prepare_other_duty,
    prepare_royal_guard_report,
    prepare_station_duty,
)

FAKE_ROUTER = '{"5":{"OPS":"fake-sheet-id"}}'

BASE_FORM = {
    "stationId": "51",
    "unitId": "หน่วยฯดอนจาน",
    "unitName": "หน่วยบริการฯดอนจาน",
    "actionBy": "test6",
    "reportDateTime": "2026-07-26T08:00",
}


class TestSchemaMatchesReportRows(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_row_matches_schema(self, prepared):
        columns = get_columns(prepared["tableName"])
        self.assertEqual(
            len(prepared["rowData"]),
            len(columns),
            f"{prepared['tableName']}: rowData มี {len(prepared['rowData'])} ช่อง "
            f"แต่ schema มี {len(columns)} ช่อง",
        )

    def test_daily_report_row_matches(self):
        self.assert_row_matches_schema(prepare_daily_report(dict(BASE_FORM)))

    def test_checkpoint_report_row_matches(self):
        self.assert_row_matches_schema(prepare_checkpoint_report(dict(BASE_FORM)))

    def test_daily_result_row_matches(self):
        self.assert_row_matches_schema(
            prepare_daily_result(dict(BASE_FORM), charges=[{"name": "ขับเร็ว", "amount": 2}])
        )

    def test_station_duty_row_matches(self):
        self.assert_row_matches_schema(prepare_station_duty(dict(BASE_FORM, startTime="2026-07-26")))

    def test_other_duty_row_matches(self):
        self.assert_row_matches_schema(
            prepare_other_duty(dict(BASE_FORM, dutyType="ทำจิตอาสา", volPolice="3"), officers=["ด.ต. ก"])
        )

    def test_accident_row_matches(self):
        self.assert_row_matches_schema(prepare_accident_report(dict(BASE_FORM, route="1", km="10")))

    def test_mission_row_matches(self):
        self.assert_row_matches_schema(prepare_mission_report(dict(BASE_FORM), selected_units=["หน่วยฯก"]))

    def test_royal_guard_row_matches(self):
        self.assert_row_matches_schema(prepare_royal_guard_report(dict(BASE_FORM, reportType="prep")))

    def test_fuel_refuel_row_matches(self):
        self.assert_row_matches_schema(
            prepare_fuel_record(dict(BASE_FORM, recordType="เติมน้ำมัน", actionDateTime="2026-07-26T09:00"))
        )

    def test_fuel_oil_change_row_matches(self):
        self.assert_row_matches_schema(
            prepare_fuel_record(
                dict(BASE_FORM, recordType="เปลี่ยนน้ำมันเครื่อง", actionDateTime="2026-07-26T09:00")
            )
        )

    def test_document_row_matches(self):
        self.assert_row_matches_schema(prepare_document_record(dict(BASE_FORM, subject="หนังสือทดสอบ")))

    def test_arrest_report_row_matches(self):
        prepared = prepare_arrest_report(
            dict(BASE_FORM, category="ยาเสพติด"),
            team_array=["ด.ต. สมชาย"],
            suspect_array=[{"name": "ก", "idCard": "1", "nat": "ไทย", "age": "30", "address": "x"}],
            charge_array=["เสพยา"],
        )
        self.assert_row_matches_schema(prepared)

    def test_every_report_table_starts_with_the_nine_system_columns(self):
        for table, columns in TABLE_COLUMNS.items():
            if table in NON_STANDARD_TABLES:
                continue
            self.assertEqual(columns[:9], SYSTEM_COLUMNS, f"{table} ไม่ได้ขึ้นต้นด้วย 9 คอลัมน์มาตรฐาน")

    def test_only_documented_tables_are_exempt_from_the_nine_column_rule(self):
        # กันไม่ให้มีใครเพิ่มตารางนอกมาตรฐานเข้ามาเงียบ ๆ
        self.assertEqual(
            NON_STANDARD_TABLES,
            frozenset(
                {"tb_HQ_Summary", "tb_FuelQuota", "tb_Users", "tb_AuditLog", "tb_PR_Keywords"}
            ),
        )

    def test_column_names_are_unique_per_table(self):
        for table, columns in TABLE_COLUMNS.items():
            self.assertEqual(len(columns), len(set(columns)), f"{table} มีชื่อคอลัมน์ซ้ำกัน")

    def test_unknown_table_raises_with_a_helpful_message(self):
        with self.assertRaises(KeyError) as ctx:
            get_columns("tb_DoesNotExist")
        self.assertIn("tb_Arrests", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
