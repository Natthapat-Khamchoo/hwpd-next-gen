"""
ฟิลด์ที่เพิ่มเข้ามาตาม requirement รอบ 16 ข้อ

test_schema.py ตรวจแค่ว่าจำนวนช่องตรงกับ schema ไฟล์นี้ตรวจว่า **ค่าลงถูกช่อง**
ซึ่งเป็นความผิดพลาดที่ชีตไม่เตือนให้เลยสักนิด
"""

import json
import unittest
from unittest import mock

from app.core.schema import get_columns
from app.services.report_service import (
    prepare_checkpoint_report,
    prepare_daily_report,
    prepare_daily_result,
    prepare_fuel_record,
)

FAKE_ROUTER = '{"5":{"OPS":"fake-sheet-id"}}'

BASE_FORM = {
    "stationId": "51",
    "unitId": "หน่วยฯดอนจาน",
    "unitName": "หน่วยบริการฯดอนจาน",
    "actionBy": "test6",
    "reportDateTime": "2026-07-26T08:00",
}


def cell(prepared, column_name):
    """ค่าในคอลัมน์ที่ระบุ อ่านตำแหน่งจาก schema ไม่ใช่เดาเลข index"""
    columns = get_columns(prepared["tableName"])
    return prepared["rowData"][columns.index(column_name)]


class ExtraFieldsTestCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)


class TestCheckpointCoordinates(ExtraFieldsTestCase):
    """ข้อ 16 — ฟอร์มตั้งด่านต้องเก็บพิกัดเพื่อขึ้นแผนที่ได้"""

    def test_lat_lng_land_in_their_own_columns(self):
        prepared = prepare_checkpoint_report(dict(BASE_FORM, lat="16.8765", lng="98.5432"))
        self.assertEqual(cell(prepared, "ละติจูด"), "16.8765")
        self.assertEqual(cell(prepared, "ลองจิจูด"), "98.5432")

    def test_missing_coordinates_stay_blank_instead_of_crashing(self):
        prepared = prepare_checkpoint_report(dict(BASE_FORM))
        self.assertEqual(cell(prepared, "ละติจูด"), "")


class TestDailyReportExtraOfficers(ExtraFieldsTestCase):
    """ข้อ 11 — เพิ่มผู้ร่วมออก ว.4 ได้หลายนายพร้อมตำแหน่ง"""

    COLUMN = "ผู้ร่วมออก ว.4 เพิ่มเติม (JSON)"

    def test_officers_are_stored_as_json_with_name_and_role(self):
        prepared = prepare_daily_report(
            dict(BASE_FORM),
            extra_officers=[
                {"name": "ด.ต. สมชาย ใจดี", "role": "พลขับสำรอง"},
                {"name": "ส.ต.ท. มานะ อดทน", "role": ""},
            ],
        )
        stored = json.loads(cell(prepared, self.COLUMN))
        self.assertEqual(stored[0], {"name": "ด.ต. สมชาย ใจดี", "role": "พลขับสำรอง"})
        self.assertEqual(stored[1]["role"], "")

    def test_plain_string_names_still_work(self):
        # ฟอร์มเดิมส่งมาเป็นรายชื่อล้วน ไม่ควรพังระหว่างที่ยังทยอยแก้ฝั่งหน้าเว็บ
        prepared = prepare_daily_report(dict(BASE_FORM), extra_officers=["ด.ต. สมชาย"])
        self.assertEqual(json.loads(cell(prepared, self.COLUMN))[0]["name"], "ด.ต. สมชาย")

    def test_blank_rows_are_dropped(self):
        prepared = prepare_daily_report(
            dict(BASE_FORM), extra_officers=["", {"name": "  "}, {"name": "ด.ต. ก"}]
        )
        self.assertEqual(len(json.loads(cell(prepared, self.COLUMN))), 1)

    def test_no_officers_leaves_the_cell_and_the_line_message_untouched(self):
        # ข้อความ LINE ของรายงานที่ไม่มีคนเพิ่ม ต้องเหมือนของเดิมเป๊ะ ไม่มีบรรทัดว่างงอก
        prepared = prepare_daily_report(dict(BASE_FORM))
        self.assertEqual(cell(prepared, self.COLUMN), "")
        self.assertNotIn("ผู้ร่วมปฏิบัติ", prepared["lineMessage"])
        self.assertNotIn("\n\nปฏิบัติหน้าที่ตั้งแต่เวลา", prepared["lineMessage"])

    def test_officers_appear_in_the_line_message(self):
        prepared = prepare_daily_report(
            dict(BASE_FORM), extra_officers=[{"name": "ด.ต. สมชาย", "role": "พลขับสำรอง"}]
        )
        self.assertIn("ผู้ร่วมปฏิบัติ ด.ต. สมชาย (พลขับสำรอง)", prepared["lineMessage"])


class TestDailyResultArrestBreakdown(ExtraFieldsTestCase):
    """ข้อ 15 — แยกยอด ว.20 เป็นตามหมายจับกับซึ่งหน้า"""

    def test_counts_are_stored_as_numbers(self):
        prepared = prepare_daily_result(dict(BASE_FORM, v20Warrant="3", v20Flagrante="7"))
        self.assertEqual(cell(prepared, "จับกุมตามหมายจับ (ราย)"), 3)
        self.assertEqual(cell(prepared, "จับกุมซึ่งหน้า (ราย)"), 7)

    def test_junk_input_counts_as_zero_rather_than_breaking_the_row(self):
        prepared = prepare_daily_result(dict(BASE_FORM, v20Warrant="ไม่ทราบ"))
        self.assertEqual(cell(prepared, "จับกุมตามหมายจับ (ราย)"), 0)


class TestFuelSlipAttachment(ExtraFieldsTestCase):
    """ข้อ 7 — แนบภาพสลิป/ใบเสร็จการเติมน้ำมัน"""

    def test_folder_url_is_written_to_the_slip_column(self):
        prepared = prepare_fuel_record(
            dict(BASE_FORM, recordType="เติมน้ำมัน", actionDateTime="2026-07-26T09:00"),
            folder_url="https://drive.google.com/x",
        )
        self.assertEqual(cell(prepared, "Slip_Attachment_Folder"), "https://drive.google.com/x")

    def test_records_without_a_slip_keep_the_default_marker(self):
        prepared = prepare_fuel_record(
            dict(BASE_FORM, recordType="เปลี่ยนน้ำมันเครื่อง", actionDateTime="2026-07-26T09:00")
        )
        self.assertEqual(cell(prepared, "Slip_Attachment_Folder"), "ไม่มีไฟล์แนบ")



class TestOverweightTruckReport(ExtraFieldsTestCase):
    """ข้อ 8 — รายงานการตรวจสอบรถบรรทุกน้ำหนักเกิน"""

    def build(self, **kwargs):
        from app.services.report_service import prepare_overweight_report

        return prepare_overweight_report(dict(BASE_FORM, **kwargs))

    def test_row_matches_the_new_table_schema(self):
        prepared = self.build(actualWeight="32000", legalWeight="25000")
        self.assertEqual(prepared["tableName"], "tb_OverweightTrucks")
        self.assertEqual(len(prepared["rowData"]), len(get_columns("tb_OverweightTrucks")))

    def test_excess_weight_and_percent_are_computed(self):
        prepared = self.build(actualWeight="32000", legalWeight="25000")
        self.assertEqual(cell(prepared, "น้ำหนักส่วนเกิน (กก.)"), 7000)
        self.assertEqual(cell(prepared, "เกินร้อยละ"), 28.0)

    def test_a_truck_within_the_limit_reports_zero_excess_not_a_negative(self):
        prepared = self.build(actualWeight="20000", legalWeight="25000")
        self.assertEqual(cell(prepared, "น้ำหนักส่วนเกิน (กก.)"), 0)
        self.assertEqual(cell(prepared, "เกินร้อยละ"), 0.0)
        self.assertIn("ไม่เกินพิกัด", prepared["lineMessage"])

    def test_a_missing_legal_weight_does_not_divide_by_zero(self):
        prepared = self.build(actualWeight="32000", legalWeight="")
        self.assertEqual(cell(prepared, "เกินร้อยละ"), 0.0)

    def test_junk_weights_count_as_zero_rather_than_breaking_the_row(self):
        prepared = self.build(actualWeight="ไม่ทราบ", legalWeight="25000")
        self.assertEqual(cell(prepared, "น้ำหนักที่ชั่งได้ (กก.)"), 0)

    def test_it_goes_into_the_approval_queue_like_other_reports(self):
        from app.services import query_service

        self.assertIn("tb_OverweightTrucks", query_service.APPROVABLE_TABLES)
        self.assertEqual(self.build()["rowData"][4], query_service.STATUS_PENDING)

    def test_the_old_document_table_is_untouched(self):
        # ข้อ 8 บอกให้ "เปลี่ยน" เมนู ไม่ใช่ให้ลบเอกสารที่ส่งเข้าระบบไปแล้ว
        from app.services.report_service import prepare_document_record

        prepared = prepare_document_record(dict(BASE_FORM, subject="หนังสือเดิม"))
        self.assertEqual(prepared["tableName"], "tb_Documents")
        self.assertEqual(len(prepared["rowData"]), len(get_columns("tb_Documents")))


if __name__ == "__main__":
    unittest.main()
