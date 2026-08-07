"""
สิ่งที่หน่วยแจ้งกลับมาหลังทดลองใช้จริง

1. ข้อความที่คัดลอกไปวางในกลุ่ม LINE ยังเป็นร่างของหน้าเว็บ ไม่ใช่ข้อความจริงที่
   backend ประกอบ จึงยังเป็นตัวยึด "[ระบบจะแนบลิงก์ไฟล์อัตโนมัติ]" แทนลิงก์โฟลเดอร์
   วงเล็บท้ายข้อความว่างเพราะหน้าเว็บไม่รู้จังหวัด และรายงานอุบัติเหตุขึ้นข้อมูลไม่ครบ
2. รายงานตั้งด่านยังไม่มีช่วงเวลาเปิด-ปิด ทำให้ตอบไม่ได้ว่าด่านไหน "ตั้งอยู่" ตอนนี้

ไฟล์นี้ล็อกพฤติกรรมทั้งสองเรื่องไว้ รวมถึงตรรกะหมุดเขียวบนแผนที่ระดับประเทศ
"""

import unittest
from datetime import datetime
from unittest import mock

from app.core.schema import get_columns
from app.services import map_service
from app.services.report_service import (
    prepare_accident_report,
    prepare_checkpoint_report,
)

FAKE_ROUTER = '{"5":{"OPS":"fake-sheet-id"}}'

BASE_FORM = {
    "stationId": "51",
    "unitId": "สามเงา",
    "actionBy": "test51",
    "reportDateTime": "2026-08-06T09:00",
}


def cell(prepared, column_name):
    columns = get_columns(prepared["tableName"])
    return prepared["rowData"][columns.index(column_name)]


class ReportTestCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)


class TestCheckpointDutyWindow(ReportTestCase):
    """ช่วงเวลาตั้งด่านที่หน่วยขอเพิ่ม"""

    def test_start_and_end_land_in_their_own_columns(self):
        prepared = prepare_checkpoint_report(
            dict(BASE_FORM, startTime="2026-08-06T18:00", endTime="2026-08-06T21:00")
        )
        self.assertEqual(cell(prepared, "เวลาเริ่มตั้งด่าน"), "2026-08-06T18:00")
        self.assertEqual(cell(prepared, "เวลาเลิกด่าน"), "2026-08-06T21:00")

    def test_the_line_message_states_the_window(self):
        prepared = prepare_checkpoint_report(
            dict(BASE_FORM, startTime="2026-08-06T18:00", endTime="2026-08-06T21:00")
        )
        self.assertIn("ตั้งด่านตั้งแต่เวลา", prepared["lineMessage"])
        self.assertIn("18.00", prepared["lineMessage"])
        self.assertIn("21.00", prepared["lineMessage"])

    def test_no_window_means_no_half_empty_line(self):
        # "ตั้งด่านตั้งแต่เวลา - ถึง -" อ่านแล้วชวนสงสัยกว่าไม่มีบรรทัดนั้นเลย
        prepared = prepare_checkpoint_report(dict(BASE_FORM))
        self.assertNotIn("ตั้งด่านตั้งแต่เวลา", prepared["lineMessage"])
        self.assertEqual(cell(prepared, "เวลาเริ่มตั้งด่าน"), "")


class TestComposedMessageIsComplete(ReportTestCase):
    """ข้อความที่ backend ประกอบต้องมีของครบ ก่อนจะถูกส่งกลับไปให้ฟอร์มคัดลอก"""

    def test_the_attachment_link_is_the_real_folder_not_a_placeholder(self):
        url = "https://drive.google.com/drive/folders/abc123"
        prepared = prepare_checkpoint_report(dict(BASE_FORM), folder_url=url)
        self.assertIn(url, prepared["lineMessage"])
        self.assertNotIn("[ระบบจะแนบลิงก์ไฟล์อัตโนมัติ]", prepared["lineMessage"])

    def test_the_accident_message_carries_every_field_the_officer_filled(self):
        form = dict(
            BASE_FORM,
            route="1",
            km="571+500",
            direction="ขาเข้า",
            locDetails="ต.วังจันทร์ อ.สามเงา จ.ตาก",
            deadCount="1",
            injuredCount="2",
            hospital="รพ.สามเงา",
            mainVehicle="รถบรรทุก 10 ล้อ 70-8717",
            oppVehicle="เก๋ง กก-1234",
            cHuman="80",
            cVehicle="20",
            solutions="กวดขันวินัยจราจร",
            govDamage="ไม่มี",
            carNumber="5115",
            jointUnits="กู้ภัยวังจันทร์",
            description="ชนท้ายขณะฝนตก",
            lat="16.4",
            lng="99.2",
        )
        message = prepare_accident_report(form)["lineMessage"]
        for expected in (
            "รพ.สามเงา",
            "รถบรรทุก 10 ล้อ 70-8717",
            "เก๋ง กก-1234",
            "กวดขันวินัยจราจร",
            "5115",
            "กู้ภัยวังจันทร์",
            "ชนท้ายขณะฝนตก",
            "16.4",
        ):
            self.assertIn(expected, message)
        # ร่างของหน้าเว็บเคยจบด้วยประโยคนี้แล้วไม่เคยมีฉบับเต็มตามมา
        self.assertNotIn("จะแสดงหลังบันทึกสำเร็จ", message)


class TestCheckpointIsOpen(unittest.TestCase):
    """หมุดเขียว = ด่านที่ยังตั้งอยู่ ตัดสินจากช่วงเวลาที่กรอก ไม่ใช่วันที่ของรายงาน"""

    def record(self, start, end):
        return {"เวลาเริ่มตั้งด่าน": start, "เวลาเลิกด่าน": end}

    def test_inside_the_window_is_open(self):
        now = datetime(2026, 8, 6, 19, 30)
        self.assertTrue(map_service.checkpoint_is_open(self.record("2026-08-06T18:00", "2026-08-06T21:00"), now))

    def test_before_and_after_the_window_are_closed(self):
        early = datetime(2026, 8, 6, 17, 0)
        late = datetime(2026, 8, 6, 22, 0)
        record = self.record("2026-08-06T18:00", "2026-08-06T21:00")
        self.assertFalse(map_service.checkpoint_is_open(record, early))
        self.assertFalse(map_service.checkpoint_is_open(record, late))

    def test_the_boundaries_count_as_open(self):
        record = self.record("2026-08-06T18:00", "2026-08-06T21:00")
        self.assertTrue(map_service.checkpoint_is_open(record, datetime(2026, 8, 6, 18, 0)))
        self.assertTrue(map_service.checkpoint_is_open(record, datetime(2026, 8, 6, 21, 0)))

    def test_a_record_without_a_window_is_never_green(self):
        # ด่านเก่าที่บันทึกก่อนมีช่องเวลา ต้องไม่ถูกแสดงว่ากำลังตั้งอยู่
        now = datetime(2026, 8, 6, 19, 30)
        self.assertFalse(map_service.checkpoint_is_open(self.record("", ""), now))

    def test_a_broken_timestamp_does_not_raise(self):
        now = datetime(2026, 8, 6, 19, 30)
        self.assertFalse(map_service.checkpoint_is_open(self.record("เมื่อวาน", "วันนี้"), now))


class TestNationalCheckpoints(unittest.TestCase):
    """รวมด่านข้ามกอง — กองที่อ่านไม่ได้ต้องถูกข้าม ไม่ใช่ทำให้ทั้งแผนที่ล้ม"""

    ROUTER = {"1": {"OPS": "sheet-1"}, "5": {"OPS": "sheet-5"}}

    def rows(self, station, start, end):
        return [
            {
                "Sys_RecordID": f"CHK-{station}",
                "Sys_Status": "Active",
                "Sys_IsActive": True,
                "Data_ActualDate": "2026-08-06",
                "Data_StationID": station,
                "Data_UnitID": "สามเงา",
                "สถานที่/จุดตรวจ": f"จุดตรวจ {station}",
                "จำนวนผู้ปฏิบัติรวม": "3",
                "รถวิทยุตรวจเขต": "ทล.1",
                "ละติจูด": "16.4",
                "ลองจิจูด": "99.2",
                "เวลาเริ่มตั้งด่าน": start,
                "เวลาเลิกด่าน": end,
            }
        ]

    def run_with(self, per_division):
        def cached_rows(spreadsheet_id, table):
            result = per_division.get(spreadsheet_id)
            if isinstance(result, Exception):
                raise result
            return result

        with mock.patch.object(map_service, "get_db_router", return_value=self.ROUTER), \
             mock.patch.object(map_service, "get_target_db_id", side_effect=lambda st: f"sheet-{st[0]}"), \
             mock.patch.object(map_service.query_service, "cached_rows", side_effect=cached_rows):
            return map_service.national_checkpoints(now=datetime(2026, 8, 6, 19, 30))

    def test_open_and_closed_checkpoints_are_labelled(self):
        data = self.run_with({
            "sheet-1": self.rows("11", "2026-08-06T18:00", "2026-08-06T21:00"),
            "sheet-5": self.rows("51", "2026-08-06T08:00", "2026-08-06T11:00"),
        })
        self.assertEqual(data["totalCount"], 2)
        self.assertEqual(data["activeCount"], 1)
        self.assertTrue(data["points"][0]["active"])

    def test_a_division_that_cannot_be_read_is_reported_not_silently_empty(self):
        data = self.run_with({
            "sheet-1": RuntimeError("อ่านชีตไม่ได้"),
            "sheet-5": self.rows("51", "2026-08-06T18:00", "2026-08-06T21:00"),
        })
        self.assertEqual(data["unavailableDivisions"], ["1"])
        self.assertEqual(data["totalCount"], 1)


if __name__ == "__main__":
    unittest.main()
