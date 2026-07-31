"""
Tests for the national rollup — the cron side that writes tb_National_Summary
and the dashboard side that reads it.
No network — the sheet reads and writes are stubbed.
"""

import json
import unittest
from unittest import mock

from app.core.schema import get_columns
from app.services import national_service, query_service
from app.services.national_service import SUMMARY_TABLE
from app.services.query_service import (
    COL_ACTUAL_DATE,
    COL_IS_ACTIVE,
    COL_RECORD_ID,
    COL_STATION_ID,
    COL_STATUS,
    COL_UNIT_ID,
)
from tests.test_query_service import row


def summary_row(record_id, division, date, active="TRUE", **sums):
    values = {
        COL_RECORD_ID: record_id, COL_STATION_ID: division, COL_UNIT_ID: f"กก.{division}",
        COL_ACTUAL_DATE: date, COL_STATUS: "Active", COL_IS_ACTIVE: active,
        "JSON_Arrests_Category": json.dumps(sums.pop("types", {}), ensure_ascii=False),
        "JSON_Charges_Detail": json.dumps(sums.pop("charges", {}), ensure_ascii=False),
        "JSON_Accident_Causes": json.dumps(sums.pop("causes", {}), ensure_ascii=False),
    }
    values.update({k: str(v) for k, v in sums.items()})
    return row(SUMMARY_TABLE, **values)


SUMMARY_ROWS = [
    get_columns(SUMMARY_TABLE),
    summary_row("S1", "1", "2026-07-27", Sum_Arrests=5, Sum_V20=100, Sum_Accidents=2,
                Sum_Missions=1, Sum_RoyalGuard=1, types={"จับกุมซึ่งหน้า": 5},
                charges={"ขับเร็ว": 20}, causes={"human": 60, "vehicle": 40}),
    summary_row("S2", "5", "2026-07-27", Sum_Arrests=8, Sum_V20=150, Sum_Accidents=3,
                types={"จับตามหมาย": 8}, charges={"ขับเร็ว": 10, "เมาแล้วขับ": 5},
                causes={"human": 30}),
    summary_row("S3", "1", "2026-07-28", Sum_Arrests=2, Sum_V20=50),
    # แถวเก่าของ (27, กก.1) ที่ Apps Script เขียนต่อท้ายไว้ — ต้องไม่ถูกนับซ้ำ
    summary_row("S1-old", "1", "2026-07-27", Sum_Arrests=999, Sum_V20=999, active="FALSE"),
    summary_row("S4", "1", "2026-06-01", Sum_Arrests=777),   # นอกช่วงวันที่
]


def stub_summary(rows=SUMMARY_ROWS):
    def fake(spreadsheet_id, table_name):
        if table_name == SUMMARY_TABLE:
            return rows
        raise query_service.sheets_service.SheetWriteError(f"ไม่พบตาราง {table_name}")

    return mock.patch.object(query_service.sheets_service, "read_table", side_effect=fake)


RANGE = ("2026-07-25", "2026-07-31")


class TestNationalSummaryRead(unittest.TestCase):
    def test_totals_sum_across_divisions_and_days(self):
        with stub_summary():
            data = national_service.national_summary(*RANGE)
        self.assertEqual(data["totals"]["arrestsCount"], 15)   # 5 + 8 + 2
        self.assertEqual(data["totals"]["v20Count"], 300)
        self.assertEqual(data["totals"]["accCount"], 5)

    def test_inactive_duplicate_rows_are_not_counted_twice(self):
        with stub_summary():
            data = national_service.national_summary(*RANGE)
        self.assertNotIn(999, [d["arrestsCount"] for d in data["byDivision"]])
        self.assertLess(data["totals"]["arrestsCount"], 999)

    def test_active_duplicates_of_one_day_keep_only_the_last_row(self):
        rows = SUMMARY_ROWS + [summary_row("S1-dup", "1", "2026-07-27", Sum_Arrests=6, Sum_V20=120)]
        with stub_summary(rows):
            data = national_service.national_summary(*RANGE)
        # กก.1 = 6 (แถวล่างสุดของวันที่ 27) + 2 (วันที่ 28) ไม่ใช่ 5 + 6 + 2
        division = {d["div"]: d for d in data["byDivision"]}["1"]
        self.assertEqual(division["arrestsCount"], 8)

    def test_dates_outside_the_range_are_excluded(self):
        with stub_summary():
            data = national_service.national_summary(*RANGE)
        self.assertNotIn("2026-06-01", [point["date"] for point in data["trend"]])
        self.assertEqual(data["totals"]["arrestsCount"], 15)   # ไม่รวม 777

    def test_by_division_is_ordered_and_named(self):
        with stub_summary():
            data = national_service.national_summary(*RANGE)
        self.assertEqual([d["div"] for d in data["byDivision"]], ["1", "5"])
        self.assertEqual(data["byDivision"][0]["divName"], "กก.1")

    def test_trend_is_sorted_by_date(self):
        with stub_summary():
            trend = national_service.national_summary(*RANGE)["trend"]
        self.assertEqual([p["date"] for p in trend], ["2026-07-27", "2026-07-28"])
        self.assertEqual(trend[0]["arrestsCount"], 13)   # กก.1 + กก.5
        self.assertEqual(trend[1]["arrestsCount"], 2)

    def test_json_breakdowns_are_merged_across_divisions(self):
        with stub_summary():
            data = national_service.national_summary(*RANGE)
        self.assertEqual(data["chargeBreakdown"]["ขับเร็ว"], 30)   # 20 + 10
        self.assertEqual(data["arrestTypeBreakdown"], {"จับกุมซึ่งหน้า": 5, "จับตามหมาย": 8})
        self.assertEqual(data["accCauseBreakdown"], {"human": 90, "vehicle": 40, "road": 0, "env": 0})

    def test_malformed_json_columns_do_not_break_the_page(self):
        rows = [get_columns(SUMMARY_TABLE), row(SUMMARY_TABLE, **{
            COL_RECORD_ID: "S9", COL_STATION_ID: "1", COL_ACTUAL_DATE: "2026-07-27",
            COL_IS_ACTIVE: "TRUE", "Sum_Arrests": "3",
            "JSON_Charges_Detail": "ไม่ใช่ json", "JSON_Arrests_Category": "[1,2]",
        })]
        with stub_summary(rows):
            data = national_service.national_summary(*RANGE)
        self.assertEqual(data["chargeBreakdown"], {})
        self.assertEqual(data["arrestTypeBreakdown"], {})
        self.assertEqual(data["totals"]["arrestsCount"], 3)

    def test_reads_one_table_only(self):
        with stub_summary() as stub:
            national_service.national_summary(*RANGE)
        self.assertEqual(stub.call_count, 1)

    def test_returns_every_key_the_dashboard_reads(self):
        with stub_summary():
            data = national_service.national_summary(*RANGE)
        for key in ("totals", "byDivision", "trend", "arrestTypeBreakdown", "chargeBreakdown", "accCauseBreakdown"):
            self.assertIn(key, data)
        for key in ("arrestsCount", "v20Count", "accCount", "royalCount", "missionCount"):
            self.assertIn(key, data["totals"])
        for key in ("div", "divName", "arrestsCount", "v20Count", "accCount", "missionCount"):
            self.assertIn(key, data["byDivision"][0])
        for key in ("human", "vehicle", "road", "env"):
            self.assertIn(key, data["accCauseBreakdown"])

    def test_empty_table_returns_zeroes_not_an_error(self):
        with stub_summary([get_columns(SUMMARY_TABLE)]):
            data = national_service.national_summary(*RANGE)
        self.assertEqual(data["totals"]["arrestsCount"], 0)
        self.assertEqual(data["byDivision"], [])
        self.assertEqual(data["trend"], [])


class TestCasualtyParsing(unittest.TestCase):
    def test_reads_dead_and_injured_out_of_the_combined_cell(self):
        self.assertEqual(
            national_service._casualties("เสียชีวิต: 2, บาดเจ็บ: 5, รพ.: กรุงเทพ"),
            (2, 5),
        )

    def test_missing_or_odd_text_counts_as_zero(self):
        for text in ("", "ไม่มีข้อมูล", None):
            self.assertEqual(national_service._casualties(text), (0, 0))


class TestSummaryRowShape(unittest.TestCase):
    def test_row_width_matches_the_schema(self):
        from collections import Counter

        values = {
            **{field: 0 for field in national_service.COUNT_COLUMNS},
            "arrestTypes": Counter(),
            "charges": Counter(),
            "causes": Counter(),
        }
        built = national_service._summary_row("5", "2026-07-27", values, "SUM-x")
        self.assertEqual(len(built), len(get_columns(SUMMARY_TABLE)))

    def test_row_starts_with_the_nine_system_columns_in_order(self):
        from collections import Counter

        values = {
            **{field: 0 for field in national_service.COUNT_COLUMNS},
            "arrestTypes": Counter(), "charges": Counter(), "causes": Counter({"human": 10}),
        }
        built = national_service._summary_row("5", "2026-07-27", values, "SUM-x")
        self.assertEqual(built[0], "SUM-x")
        self.assertEqual(built[3], "SYSTEM_CRON")
        self.assertEqual(built[4], "Active")
        self.assertIs(built[5], True)
        self.assertEqual(built[6], "2026-07-27")
        self.assertEqual(built[7], "5")
        self.assertEqual(built[8], "กก.5")
        self.assertEqual(json.loads(built[-1])["human"], 10)


class TestAggregateWrites(unittest.TestCase):
    """
    การรวมยอดต้องเขียนทับแถวเดิมของ (วันที่, กก.) ไม่ใช่ต่อท้ายทุกรอบแบบที่
    Apps Script ทำไว้ จนตารางมีแถวซ้ำของวันเดียวกันหลายสิบแถว
    """

    def _run(self, existing_rows, fresh, row_count=1000):
        worksheet = mock.Mock()
        # ชีตจริงมีเพดานจำนวนแถว การเขียนต่อท้ายต้องเทียบกับค่านี้ก่อน ไม่งั้น Google
        # ตอบ 400 exceeds grid limits แล้วทิ้งทั้ง batch
        worksheet.row_count = row_count
        with mock.patch.object(national_service, "_configured_divisions", return_value=["1"]), \
             mock.patch.object(national_service, "aggregate_division", return_value=fresh), \
             mock.patch.object(query_service.sheets_service, "read_table", return_value=existing_rows), \
             mock.patch.object(query_service.sheets_service, "get_worksheet", return_value=worksheet), \
             mock.patch.object(
                 query_service.sheets_service, "with_backoff",
                 side_effect=lambda fn, *a, **kw: fn(*a, **kw)):
            result = national_service.aggregate_national("2026-07-27", "2026-07-27")
        return result, worksheet

    def _fresh_day(self):
        from collections import Counter

        return {
            "2026-07-27": {
                **{field: 1 for field in national_service.COUNT_COLUMNS},
                "arrestTypes": Counter(), "charges": Counter(), "causes": Counter(),
            }
        }

    def test_new_day_is_appended(self):
        result, worksheet = self._run([get_columns(SUMMARY_TABLE)], self._fresh_day())
        self.assertEqual((result["appended"], result["replaced"]), (1, 0))
        worksheet.update.assert_called_once()
        worksheet.batch_update.assert_not_called()
        worksheet.add_rows.assert_not_called()

    def test_sheet_is_grown_when_the_new_row_would_fall_outside_it(self):
        """
        ชีตเต็มแล้วต้องขยายก่อนเขียน ไม่ใช่ปล่อยให้ Google ตอบ 400 exceeds grid limits

        เคยเกิดจริงบนชีตที่ใช้งานอยู่: แถวเต็ม 1023 การรวมยอดจึงเขียนแถวใหม่ไม่ได้ทั้ง
        batch กก. ที่มีแถวของวันนั้นอยู่แล้วรอดเพราะไปทางเขียนทับ ที่เหลือหายจากหน้า
        ผบก. โดยไม่มี error ให้ใครเห็น เพราะ endpoint ตอบ 202 ไปก่อนแล้ว
        """
        existing = [get_columns(SUMMARY_TABLE)] + [
            summary_row(f"S{i}", "9", f"2026-06-{i:02d}") for i in range(1, 10)
        ]
        # แถวว่างถัดไปคือ 11 แต่ชีตมีแค่ 10 แถว
        result, worksheet = self._run(existing, self._fresh_day(), row_count=10)

        self.assertEqual((result["appended"], result["replaced"]), (1, 0))
        worksheet.add_rows.assert_called_once()
        self.assertGreater(worksheet.add_rows.call_args.args[0], 0)
        worksheet.update.assert_called_once()

    def test_existing_day_is_written_over_in_place(self):
        existing = [get_columns(SUMMARY_TABLE), summary_row("S1", "1", "2026-07-27", Sum_Arrests=5)]
        result, worksheet = self._run(existing, self._fresh_day())
        self.assertEqual((result["appended"], result["replaced"]), (0, 1))
        worksheet.update.assert_not_called()
        ranges = [u["range"] for u in worksheet.batch_update.call_args.args[0]]
        self.assertTrue(ranges[0].startswith("A2:"), ranges)

    def test_older_duplicates_of_the_same_day_are_deactivated(self):
        existing = [
            get_columns(SUMMARY_TABLE),
            summary_row("S1", "1", "2026-07-27", Sum_Arrests=5),
            summary_row("S1b", "1", "2026-07-27", Sum_Arrests=5),
            summary_row("S1c", "1", "2026-07-27", Sum_Arrests=5),
        ]
        result, worksheet = self._run(existing, self._fresh_day())
        self.assertEqual(result["deactivated"], 2)
        updates = worksheet.batch_update.call_args.args[0]
        # แถวล่างสุด (4) ถูกเขียนทับ ส่วนแถว 2 และ 3 ถูกปิด
        self.assertTrue(updates[0]["range"].startswith("A4:"))
        self.assertEqual([u["values"] for u in updates[1:]], [[[False]], [[False]]])

    def test_rerunning_does_not_grow_the_table(self):
        existing = [get_columns(SUMMARY_TABLE), summary_row("S1", "1", "2026-07-27", Sum_Arrests=5)]
        first, _ = self._run(existing, self._fresh_day())
        second, _ = self._run(existing, self._fresh_day())
        self.assertEqual(first["appended"], 0)
        self.assertEqual(second["appended"], 0)


class TestDeactivateDuplicates(unittest.TestCase):
    def _run(self, rows):
        worksheet = mock.Mock()
        with mock.patch.object(query_service.sheets_service, "read_table", return_value=rows), \
             mock.patch.object(query_service.sheets_service, "get_worksheet", return_value=worksheet), \
             mock.patch.object(
                 query_service.sheets_service, "with_backoff",
                 side_effect=lambda fn, *a, **kw: fn(*a, **kw)):
            result = national_service.deactivate_duplicates()
        return result, worksheet

    def test_keeps_the_last_row_of_each_day_and_division(self):
        rows = [
            get_columns(SUMMARY_TABLE),
            summary_row("A", "1", "2026-07-27"),
            summary_row("B", "1", "2026-07-27"),
            summary_row("C", "1", "2026-07-27"),
            summary_row("D", "5", "2026-07-27"),
        ]
        result, worksheet = self._run(rows)
        self.assertEqual(result, {"keys": 2, "deactivated": 2})
        ranges = [u["range"] for u in worksheet.batch_update.call_args.args[0]]
        # แถว 2 และ 3 ถูกปิด แถว 4 (ล่างสุดของ กก.1) และแถว 5 ยังอยู่
        self.assertEqual(sorted(ranges), ["F2", "F3"])

    def test_already_clean_table_writes_nothing(self):
        rows = [get_columns(SUMMARY_TABLE), summary_row("A", "1", "2026-07-27")]
        result, worksheet = self._run(rows)
        self.assertEqual(result["deactivated"], 0)
        worksheet.batch_update.assert_not_called()

    def test_rows_already_inactive_are_left_alone(self):
        rows = [
            get_columns(SUMMARY_TABLE),
            summary_row("A", "1", "2026-07-27", active="FALSE"),
            summary_row("B", "1", "2026-07-27"),
        ]
        result, _ = self._run(rows)
        self.assertEqual(result["deactivated"], 0)


if __name__ == "__main__":
    unittest.main()
