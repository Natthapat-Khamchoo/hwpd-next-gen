"""
Tests for the daily and division summaries.
No network — the sheet reads are stubbed.
"""

import json
import unittest
from unittest import mock

from app.core.schema import get_columns
from app.services import query_service
from app.services.query_service import (
    COL_ACTUAL_DATE,
    COL_IS_ACTIVE,
    COL_RECORD_ID,
    COL_STATION_ID,
    COL_STATUS,
)
from tests.test_query_service import DB_ID, row, stub_router, stub_sheets


def result(record_id, station, date, v43=0, v42=0, v20=0, service=0, status="Approved", charges=""):
    return row("tb_DailyResult", **{
        COL_RECORD_ID: record_id, COL_STATION_ID: station, COL_ACTUAL_DATE: date,
        COL_STATUS: status, COL_IS_ACTIVE: "TRUE",
        "ยอด ว.43": str(v43), "ยอด ว.42": str(v42), "ยอด ว.20": str(v20),
        "ยอด บริการ": str(service), "Charges_Detail": charges,
    })


def arrest(record_id, station, date, charges="", seized=None, status="Approved"):
    return row("tb_Arrests", **{
        COL_RECORD_ID: record_id, COL_STATION_ID: station, COL_ACTUAL_DATE: date,
        COL_STATUS: status, COL_IS_ACTIVE: "TRUE",
        "ข้อหาทั้งหมด": charges,
        "ของกลาง (JSON มีโครงสร้าง)": json.dumps(seized or [], ensure_ascii=False),
    })


RESULTS = [
    get_columns("tb_DailyResult"),
    result("R1", "51", "2026-07-27", v43=10, v42=2, v20=3, service=5, charges="ขับเร็ว (2) | ไม่สวมหมวก (1)"),
    result("R2", "51", "2026-07-28", v43=20, v42=1, v20=4, service=7, charges="ขับเร็ว (3)"),
    result("R3", "52", "2026-07-27", v43=30, v42=3, v20=5, service=9),
    result("R4", "51", "2026-07-27", v43=999, status="Pending"),          # ยังไม่ตรวจ
    result("R5", "51", "2026-07-01", v43=888),                            # นอกช่วงวันที่
]

ARRESTS = [
    get_columns("tb_Arrests"),
    arrest("A1", "51", "2026-07-27", charges="1. ยาเสพติด", seized=[{"name": "ยาบ้า", "qty": "200"}]),
    arrest("A2", "52", "2026-07-28", charges="1. เมาแล้วขับ", seized=[{"name": "ยาบ้า"}, {"name": "อาวุธปืน"}]),
    arrest("A3", "51", "2026-07-27", status="Pending"),
]

ACCIDENTS = [
    get_columns("tb_Accidents"),
    row("tb_Accidents", **{
        COL_RECORD_ID: "AC1", COL_STATION_ID: "51", COL_ACTUAL_DATE: "2026-07-27",
        COL_STATUS: "Approved", COL_IS_ACTIVE: "TRUE",
        "% สาเหตุ": "คน:60%, รถ:20%, ถนน:15%, แวดล้อม:5%",
    }),
]

OTHER = [
    get_columns("tb_OtherDuties"),
    row("tb_OtherDuties", **{
        COL_RECORD_ID: "O1", COL_STATION_ID: "51", COL_ACTUAL_DATE: "2026-07-27",
        COL_STATUS: "Approved", COL_IS_ACTIVE: "TRUE", "การปฏิบัติ": "ทำจิตอาสา",
    }),
    row("tb_OtherDuties", **{
        COL_RECORD_ID: "O2", COL_STATION_ID: "51", COL_ACTUAL_DATE: "2026-07-27",
        COL_STATUS: "Approved", COL_IS_ACTIVE: "TRUE", "การปฏิบัติ": "ตรวจเขต",
    }),
]

# ภารกิจกับรับเสด็จเคยไม่มีใน fixture ทั้งที่ทั้งสองสรุปอ่านสองตารางนี้ด้วย
# ช่องโหว่นั้นทำให้ NameError ใน _station_summary หลุดขึ้น production ไปหนึ่งรอบ
MISSIONS = [
    get_columns("tb_Missions"),
    row("tb_Missions", **{
        COL_RECORD_ID: "M1", COL_STATION_ID: "51", COL_ACTUAL_DATE: "2026-07-27",
        COL_STATUS: "Active", COL_IS_ACTIVE: "TRUE", "รายละเอียดภารกิจ": "ตรวจจุดเสี่ยง",
    }),
    row("tb_Missions", **{
        COL_RECORD_ID: "M2", COL_STATION_ID: "52", COL_ACTUAL_DATE: "2026-07-28",
        COL_STATUS: "Active", COL_IS_ACTIVE: "TRUE", "รายละเอียดภารกิจ": "กวดขันวินัยจราจร",
    }),
]

ROYAL_GUARD = [
    get_columns("tb_RoyalGuard"),
    row("tb_RoyalGuard", **{
        COL_RECORD_ID: "RG1", COL_STATION_ID: "51", COL_ACTUAL_DATE: "2026-07-27",
        COL_STATUS: "Approved", COL_IS_ACTIVE: "TRUE", "ชื่อภารกิจ": "รับเสด็จ",
    }),
]

ALL_TABLES = {
    "tb_DailyResult": RESULTS,
    "tb_Arrests": ARRESTS,
    "tb_Accidents": ACCIDENTS,
    "tb_OtherDuties": OTHER,
    "tb_Missions": MISSIONS,
    "tb_RoyalGuard": ROYAL_GUARD,
}

RANGE = ("2026-07-25", "2026-07-31")


class TestParsers(unittest.TestCase):
    def test_charge_numbering_is_stripped_before_counting(self):
        self.assertEqual(
            query_service._split_charges("1. ขับเร็ว\n2) ไม่สวมหมวก\n  3.  เมาแล้วขับ  "),
            ["ขับเร็ว", "ไม่สวมหมวก", "เมาแล้วขับ"],
        )

    def test_same_charge_at_different_positions_counts_as_one(self):
        first = query_service._split_charges("1. ขับเร็ว")
        second = query_service._split_charges("3. ขับเร็ว")
        self.assertEqual(first, second)

    def test_blank_charge_text_yields_nothing(self):
        self.assertEqual(query_service._split_charges(""), [])
        self.assertEqual(query_service._split_charges("   \n  "), [])
        self.assertEqual(query_service._split_charges("-"), [])

    def test_daily_result_charges_use_pipes_and_carry_their_own_count(self):
        # prepare_daily_result เขียน "ชื่อ (จำนวน)" คั่นด้วย | ไม่ใช่หนึ่งบรรทัดต่อข้อหา
        self.assertEqual(
            query_service._split_charge_counts("ขับเร็ว (12) | ไม่สวมหมวก (5)"),
            [("ขับเร็ว", 12), ("ไม่สวมหมวก", 5)],
        )

    def test_daily_result_charge_without_a_count_is_one(self):
        self.assertEqual(query_service._split_charge_counts("ขับเร็ว"), [("ขับเร็ว", 1)])

    def test_placeholder_dash_is_not_a_charge(self):
        self.assertEqual(query_service._split_charge_counts("-"), [])
        self.assertEqual(query_service._split_charge_counts(""), [])

    def test_the_same_charge_from_both_columns_lands_in_one_bucket(self):
        """
        ใบจับกุมเขียน "1. ขับเร็ว" ส่วนผลการปฏิบัติเขียน "ขับเร็ว (2)"
        ถ้าอ่านคนละแบบ ข้อหาเดียวกันจะโผล่สองรายการในกราฟ
        """
        from_arrest = query_service._split_charges("1. ขับเร็ว")
        from_result = [name for name, _ in query_service._split_charge_counts("ขับเร็ว (2)")]
        self.assertEqual(from_arrest, from_result)

    def test_seized_names_come_from_the_json_column(self):
        raw = json.dumps([{"name": "ยาบ้า", "qty": "200"}, {"name": "อาวุธปืน"}], ensure_ascii=False)
        self.assertEqual(query_service._split_seized(raw), ["ยาบ้า", "อาวุธปืน"])

    def test_malformed_seized_json_is_ignored_not_fatal(self):
        for raw in ("", "ไม่ใช่ json", "{}", '"a"', '[{"qty": "1"}]'):
            self.assertEqual(query_service._split_seized(raw), [])

    def test_accident_causes_are_read_as_percentages(self):
        from collections import Counter

        causes: Counter = Counter()
        query_service._add_causes("คน:60%, รถ:20%, ถนน:15%, แวดล้อม:5%", causes)
        self.assertEqual(dict(causes), {"human": 60, "vehicle": 20, "road": 15, "env": 5})

    def test_missing_cause_fields_are_skipped(self):
        from collections import Counter

        causes: Counter = Counter()
        query_service._add_causes("คน:100%", causes)
        self.assertEqual(dict(causes), {"human": 100})


class TestDailySummary(unittest.TestCase):
    def test_totals_cover_one_station_within_the_date_range(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            data = query_service.daily_summary("51", *RANGE)
        self.assertEqual(data["v43"], 30)   # R1 + R2, ไม่รวม R4 (Pending) และ R5 (นอกช่วง)
        self.assertEqual(data["v42"], 3)
        self.assertEqual(data["v20"], 7)
        self.assertEqual(data["service"], 12)

    def test_another_station_is_not_mixed_in(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            data = query_service.daily_summary("52", *RANGE)
        self.assertEqual(data["v43"], 30)   # R3 เท่านั้น
        self.assertEqual(data["v20"], 5)

    def test_charges_text_is_ordered_most_frequent_first(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            text = query_service.daily_summary("51", *RANGE)["chargesText"]
        lines = text.splitlines()
        # ขับเร็ว = 2 (R1) + 3 (R2) — จำนวนในวงเล็บถูกนับ ไม่ใช่นับแถวละหนึ่ง
        self.assertEqual(lines[0], "ขับเร็ว = 5")
        self.assertIn("ไม่สวมหมวก = 1", lines)
        self.assertIn("ยาเสพติด = 1", lines)   # ข้อหาจากใบจับกุมนับรวมด้วย
        self.assertEqual(len([l for l in lines if l.startswith("ขับเร็ว")]), 1)

    def test_empty_range_returns_zeroes_not_an_error(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            data = query_service.daily_summary("51", "2020-01-01", "2020-01-02")
        self.assertEqual((data["v43"], data["v20"], data["chargesText"]), (0, 0, ""))

    def test_returns_every_field_the_form_reads(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            data = query_service.daily_summary("51", *RANGE)
        for field in ("v43", "service", "v42", "v20", "chargesText"):
            self.assertIn(field, data)


class TestDivisionSummary(unittest.TestCase):
    def test_lists_every_station_of_the_division_even_with_no_data(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            data = query_service.division_summary("50", *RANGE)
        self.assertEqual([s["station"] for s in data["byStation"]], ["51", "52", "53", "54", "55", "56"])

    def test_per_station_figures_are_not_pooled(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            by_station = {s["station"]: s for s in query_service.division_summary("50", *RANGE)["byStation"]}
        self.assertEqual(by_station["51"]["v43"], 30)
        self.assertEqual(by_station["52"]["v43"], 30)
        self.assertEqual(by_station["53"]["v43"], 0)

    def test_totals_equal_the_sum_of_the_stations(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            data = query_service.division_summary("50", *RANGE)
        for key in ("v43", "v20", "arrest", "service", "royalGuard", "volunteer"):
            self.assertEqual(
                data["totals"][key],
                sum(s[key] for s in data["byStation"]),
                f"ยอดรวมของ {key} ไม่ตรงกับผลรวมรายสถานี",
            )

    def test_arrests_are_counted_per_station(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            by_station = {s["station"]: s for s in query_service.division_summary("50", *RANGE)["byStation"]}
        self.assertEqual(by_station["51"]["arrest"], 1)   # A3 ยัง Pending
        self.assertEqual(by_station["52"]["arrest"], 1)

    def test_only_volunteer_duties_count_towards_volunteer(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            by_station = {s["station"]: s for s in query_service.division_summary("50", *RANGE)["byStation"]}
        self.assertEqual(by_station["51"]["volunteer"], 1)   # O2 เป็นตรวจเขต ไม่ใช่จิตอาสา

    def test_seized_breakdown_counts_across_stations(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            data = query_service.division_summary("50", *RANGE)
        self.assertEqual(data["seizedBreakdown"], {"ยาบ้า": 2, "อาวุธปืน": 1})

    def test_accident_causes_are_reported(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            data = query_service.division_summary("50", *RANGE)
        self.assertEqual(data["accCauseBreakdown"], {"human": 60, "vehicle": 20, "road": 15, "env": 5})
        self.assertEqual(data["totals"]["accident"], 1)

    def test_trend_is_sorted_by_date_with_no_blank_bucket(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            trend = query_service.division_summary("50", *RANGE)["trend"]
        self.assertEqual([point["date"] for point in trend], ["2026-07-27", "2026-07-28"])
        self.assertEqual(trend[0]["arrest"], 1)
        self.assertEqual(trend[1]["arrest"], 1)

    def test_station_labels_are_short_enough_for_a_chart_axis(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            names = [s["name"] for s in query_service.division_summary("50", *RANGE)["byStation"]]
        self.assertEqual(names[0], "ส.ทล.1")
        self.assertTrue(all(len(name) <= 10 for name in names))

    def test_reads_each_table_once_regardless_of_station_count(self):
        with stub_router(), stub_sheets(ALL_TABLES) as stub:
            query_service.division_summary("50", *RANGE)
        # 5 ตารางสรุป + tb_Accidents ไม่ใช่คูณจำนวนสถานี
        self.assertEqual(stub.call_count, len(query_service.SUMMARY_TABLES) + 1)

    def test_returns_every_key_the_dashboards_read(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            data = query_service.division_summary("50", *RANGE)
        for key in ("totals", "byStation", "seizedBreakdown", "chargeBreakdown", "accCauseBreakdown", "trend"):
            self.assertIn(key, data)
        for key in ("v43", "v20", "arrest", "service", "volunteer", "royalGuard", "accident", "mission"):
            self.assertIn(key, data["totals"])
        for key in ("station", "name", "v43", "v20", "arrest", "service", "royalGuard", "volunteer"):
            self.assertIn(key, data["byStation"][0])

    def test_divisions_with_fewer_stations_are_handled(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            data = query_service.division_summary("80", *RANGE)
        self.assertEqual(len(data["byStation"]), 4)   # กก.8 มี 4 สถานี


class TestSeizedItemsReachTheSheet(unittest.TestCase):
    """
    ฟอร์มส่ง seizedItems มาเป็นอาร์เรย์แยก ไม่ใช่ค่าใน formData เดิมจึงไม่มีใครรับ
    แล้วคอลัมน์ JSON ว่างตลอด ทำให้กราฟของกลางไม่มีข้อมูล
    """

    def test_arrest_row_carries_the_structured_items(self):
        from app.core.schema import get_columns as columns
        from app.services.report_service import prepare_arrest_report

        prepared = prepare_arrest_report(
            {"stationId": "51", "actionBy": "st51"},
            team_array=[],
            suspect_array=[],
            charge_array=["ยาเสพติด"],
            seized_items=[{"name": "ยาบ้า", "qty": "200", "note": ""}],
        )
        index = columns("tb_Arrests").index("ของกลาง (JSON มีโครงสร้าง)")
        self.assertEqual(query_service._split_seized(prepared["rowData"][index]), ["ยาบ้า"])

    def test_items_without_a_name_are_dropped(self):
        from app.core.schema import get_columns as columns
        from app.services.report_service import prepare_arrest_report

        prepared = prepare_arrest_report(
            {"stationId": "51"}, team_array=[], suspect_array=[], charge_array=[],
            seized_items=[{"qty": "5"}, {"name": "  "}],
        )
        index = columns("tb_Arrests").index("ของกลาง (JSON มีโครงสร้าง)")
        self.assertEqual(prepared["rowData"][index], "")


if __name__ == "__main__":
    unittest.main()


class TestMissionAndRoyalGuardCounters(unittest.TestCase):
    """
    ทั้งสองสรุปวนตารางชุดเดียวกันแต่เก็บผลคนละแบบ — สรุปสถานีเดียวมีแต่ totals
    ส่วนสรุประดับ กก. มี bucket รายสถานีด้วย เผลอคัดลอกโค้ดข้ามกันเมื่อไหร่พังทันที
    """

    def test_station_summary_counts_missions_without_a_per_station_bucket(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            data = query_service.daily_summary("51", *RANGE)
        self.assertIn("v43", data)

    def test_division_summary_splits_missions_per_station(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            data = query_service.division_summary("50", *RANGE)
        by_station = {s["station"]: s for s in data["byStation"]}
        self.assertEqual(by_station["51"]["mission"], 1)
        self.assertEqual(by_station["52"]["mission"], 1)
        self.assertEqual(by_station["53"]["mission"], 0)
        self.assertEqual(data["totals"]["mission"], 2)

    def test_royal_guard_is_counted_on_both_paths(self):
        with stub_router(), stub_sheets(ALL_TABLES):
            station = query_service.daily_summary("51", *RANGE)
            division = query_service.division_summary("50", *RANGE)
        self.assertEqual(division["totals"]["royalGuard"], 1)
        self.assertIn("v43", station)
