"""
พิกัดสำหรับหน้าแผนที่ (requirement ข้อ 4)

จุดที่ต้องระวังที่สุดคือพิกัดเสีย — ชีตเก็บทุกอย่างเป็นข้อความ ช่องละติจูดจึงมีทั้ง
ค่าว่าง ขีด เลขไมล์ที่กรอกผิดช่อง และค่าที่สลับ lat/lng กัน ถ้าปล่อยผ่านไปถึงหน้าเว็บ
แผนที่จะซูมออกไปกลางมหาสมุทรโดยที่ไม่มีใครรู้ว่าเพราะแถวไหน
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("SESSION_SECRET", "test-secret-for-map-tests")

from app.services import map_service, query_service  # noqa: E402

FAKE_ROUTER = '{"5":{"OPS":"sheet-div-5"}}'


def arrest(record_id, lat, lng, station="51", charges="1. เสพยาเสพติด\n2. ขับเร็ว", date="2026-08-01", unit="สามเงา"):
    return {
        query_service.COL_RECORD_ID: record_id,
        query_service.COL_STATUS: query_service.STATUS_APPROVED,
        query_service.COL_IS_ACTIVE: True,
        query_service.COL_ACTUAL_DATE: date,
        query_service.COL_STATION_ID: station,
        query_service.COL_UNIT_ID: unit,
        "หัวข้อการจับกุม": "จับกุมยาเสพติด",
        "ข้อหาทั้งหมด": charges,
        "ละติจูด": lat,
        "ลองจิจูด": lng,
    }


def checkpoint(record_id, lat, lng, station="51", date="2026-08-01"):
    return {
        query_service.COL_RECORD_ID: record_id,
        query_service.COL_STATUS: query_service.STATUS_APPROVED,
        query_service.COL_IS_ACTIVE: True,
        query_service.COL_ACTUAL_DATE: date,
        query_service.COL_STATION_ID: station,
        query_service.COL_UNIT_ID: "สามเงา",
        "สถานที่/จุดตรวจ": "ทล.1 กม.571",
        "จำนวนผู้ปฏิบัติรวม": "4",
        "รถวิทยุตรวจเขต": "5115",
        "ละติจูด": lat,
        "ลองจิจูด": lng,
    }


class MapTestCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        mock.patch.object(query_service, "prefetch").start()
        self.addCleanup(mock.patch.stopall)

    def run_with(self, tables, **kwargs):
        with mock.patch.object(query_service, "cached_rows", side_effect=lambda _s, t: tables.get(t, [])):
            return map_service.map_points(kwargs.pop("station_id", "51"), **kwargs)


class TestCoordinateHygiene(MapTestCase):
    def test_blank_and_dash_coordinates_are_dropped_without_counting_as_errors(self):
        result = self.run_with(
            {"tb_Arrests": [arrest("A1", "", ""), arrest("A2", "-", "-")]},
            layers=["crime"],
        )
        self.assertEqual(result["counts"]["crime"], 0)
        # ช่องว่างคือ "ยังไม่ได้กรอก" ไม่ใช่ "กรอกผิด" จึงไม่ควรไปโผล่ในคำเตือน
        self.assertEqual(result["skippedInvalidCoordinates"], 0)

    def test_coordinates_outside_thailand_are_reported_not_hidden(self):
        # 98.5 / 16.8 คือค่าที่สลับ lat กับ lng กัน ซึ่งเจอบ่อยเวลาคัดลอกจาก Google Maps
        result = self.run_with({"tb_Arrests": [arrest("A1", "98.5432", "16.8765")]}, layers=["crime"])
        self.assertEqual(result["counts"]["crime"], 0)
        self.assertEqual(result["skippedInvalidCoordinates"], 1)

    def test_mileage_typed_into_the_latitude_box_is_rejected(self):
        result = self.run_with({"tb_Arrests": [arrest("A1", "120450", "98.5")]}, layers=["crime"])
        self.assertEqual(result["skippedInvalidCoordinates"], 1)

    def test_text_that_is_not_a_number_is_dropped_without_raising(self):
        result = self.run_with({"tb_Arrests": [arrest("A1", "ไม่ทราบ", "98.5")]}, layers=["crime"])
        self.assertEqual(result["counts"]["crime"], 0)

    def test_valid_thai_coordinates_come_through_as_floats(self):
        result = self.run_with({"tb_Arrests": [arrest("A1", "16.8765", "98.5432")]}, layers=["crime"])
        point = result["points"][0]
        self.assertEqual((point["lat"], point["lng"]), (16.8765, 98.5432))
        self.assertIsInstance(point["lat"], float)


class TestLayerSelection(MapTestCase):
    def test_only_requested_layers_are_read(self):
        tables = {"tb_Arrests": [arrest("A1", "16.8", "98.5")], "tb_Checkpoints": [checkpoint("C1", "16.9", "98.6")]}
        with mock.patch.object(query_service, "cached_rows", side_effect=lambda _s, t: tables.get(t, [])) as reader:
            map_service.map_points("51", layers=["crime"])
        # ชั้นที่ผู้ใช้ปิดไว้ต้องไม่ถูกอ่านจากชีตเลย ไม่ใช่อ่านมาแล้วค่อยกรองทิ้ง
        self.assertEqual([call.args[1] for call in reader.call_args_list], ["tb_Arrests"])

    def test_no_layers_given_means_all_three(self):
        result = self.run_with({})
        self.assertEqual(set(result["counts"]), {"crime", "checkpoint", "accident"})

    def test_unknown_layer_names_fall_back_to_all_three(self):
        result = self.run_with({}, layers=["ufo"])
        self.assertEqual(set(result["counts"]), {"crime", "checkpoint", "accident"})

    def test_one_unreadable_table_does_not_empty_the_whole_map(self):
        def reader(_sheet, table):
            if table == "tb_Arrests":
                raise RuntimeError("แท็บหาย")
            return [checkpoint("C1", "16.9", "98.6")]

        with mock.patch.object(query_service, "cached_rows", side_effect=reader):
            result = map_service.map_points("51", layers=["crime", "checkpoint"])

        self.assertEqual(result["counts"]["crime"], 0)
        self.assertEqual(result["counts"]["checkpoint"], 1)


class TestFilters(MapTestCase):
    def test_charge_filter_narrows_the_crime_layer(self):
        tables = {
            "tb_Arrests": [
                arrest("A1", "16.8", "98.5", charges="1. เสพยาเสพติด"),
                arrest("A2", "16.9", "98.6", charges="1. ขับเร็วเกินกำหนด"),
            ]
        }
        result = self.run_with(tables, layers=["crime"], charge="เสพยาเสพติด")
        self.assertEqual([p["recordId"] for p in result["points"]], ["A1"])

    def test_charge_filter_leaves_checkpoints_alone(self):
        # ด่านไม่มีข้อหาผูกอยู่ ถ้าเอาตัวกรองนี้ไปตัดด้วย หมุดด่านจะหายหมดทั้งที่ไม่เกี่ยว
        tables = {"tb_Checkpoints": [checkpoint("C1", "16.9", "98.6")]}
        result = self.run_with(tables, layers=["checkpoint"], charge="เสพยาเสพติด")
        self.assertEqual(result["counts"]["checkpoint"], 1)

    def test_date_range_excludes_rows_outside_it(self):
        tables = {
            "tb_Arrests": [
                arrest("A1", "16.8", "98.5", date="2026-07-01"),
                arrest("A2", "16.9", "98.6", date="2026-08-15"),
            ]
        }
        result = self.run_with(tables, layers=["crime"], start="2026-08-01", end="2026-08-31")
        self.assertEqual([p["recordId"] for p in result["points"]], ["A2"])

    def test_unit_filter_matches_the_unit_column(self):
        tables = {"tb_Arrests": [arrest("A1", "16.8", "98.5", unit="สามเงา"), arrest("A2", "16.9", "98.6", unit="แม่สอด")]}
        result = self.run_with(tables, layers=["crime"], unit="แม่สอด")
        self.assertEqual([p["recordId"] for p in result["points"]], ["A2"])

    def test_a_station_account_only_sees_its_own_station(self):
        tables = {"tb_Arrests": [arrest("A1", "16.8", "98.5", station="51"), arrest("A2", "16.9", "98.6", station="52")]}
        result = self.run_with(tables, layers=["crime"], station_id="51")
        self.assertEqual([p["recordId"] for p in result["points"]], ["A1"])

    def test_a_division_account_sees_every_station_in_its_division(self):
        tables = {"tb_Arrests": [arrest("A1", "16.8", "98.5", station="51"), arrest("A2", "16.9", "98.6", station="52")]}
        result = self.run_with(tables, layers=["crime"], station_id="50")
        self.assertEqual({p["recordId"] for p in result["points"]}, {"A1", "A2"})


class TestRecordVisibility(MapTestCase):
    def test_pending_records_stay_off_the_map(self):
        row = arrest("A1", "16.8", "98.5")
        row[query_service.COL_STATUS] = query_service.STATUS_PENDING
        self.assertEqual(self.run_with({"tb_Arrests": [row]}, layers=["crime"])["counts"]["crime"], 0)

    def test_canceled_records_stay_off_the_map(self):
        row = arrest("A1", "16.8", "98.5")
        row[query_service.COL_IS_ACTIVE] = "FALSE"
        self.assertEqual(self.run_with({"tb_Arrests": [row]}, layers=["crime"])["counts"]["crime"], 0)

    def test_points_come_back_newest_first(self):
        tables = {
            "tb_Arrests": [
                arrest("OLD", "16.8", "98.5", date="2026-07-01"),
                arrest("NEW", "16.9", "98.6", date="2026-08-15"),
            ]
        }
        result = self.run_with(tables, layers=["crime"])
        self.assertEqual([p["recordId"] for p in result["points"]], ["NEW", "OLD"])


if __name__ == "__main__":
    unittest.main()
