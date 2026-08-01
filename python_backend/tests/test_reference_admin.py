"""
แก้ตารางอ้างอิงต้องแตะเฉพาะแถวที่ตั้งใจ และต้องรับชื่อตารางจากทะเบียนเท่านั้น

endpoint เดียวรับ kind มาจาก URL ถ้าปล่อยให้ชื่อชีตมาจากผู้เรียกได้ จะกลายเป็นช่อง
เขียนทับชีตอะไรก็ได้ในไฟล์กลาง รวมถึง tb_Users
"""

import unittest
from unittest import mock

from app.services import reference_admin_service as svc

CHARGES = [
    ["ชื่อข้อหา", "crimeGroup (กลุ่มคดี)", "reportTags (ป้ายหมวดรายงาน)", "sixteenBase (ฐาน 16 ศปอร.)", "isActive"],
    ["ขับรถเร็วเกินกว่าที่กฎหมายกำหนด", "จราจร", "", "", ""],
    ["มียาเสพติดไว้ในครอบครอง", "ยาเสพติด", "DRUG", "", "TRUE"],
]


class TestReferenceAdmin(unittest.TestCase):
    def setUp(self):
        self.ws = mock.Mock()
        for p in (
            mock.patch.object(svc.sheets_service, "read_table", return_value=CHARGES),
            mock.patch.object(svc.sheets_service, "get_worksheet", return_value=self.ws),
            mock.patch.object(svc.sheets_service, "with_backoff", side_effect=lambda fn, *a, **kw: fn(*a, **kw)),
            mock.patch.object(svc.reference_service, "reset_cache"),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _call(self):
        return self.ws.update.call_args.kwargs

    def test_unknown_table_is_refused(self):
        with self.assertRaises(svc.ReferenceTableError):
            svc.list_rows("tb_Users")
        with self.assertRaises(svc.ReferenceTableError):
            svc.upsert("tb_Users", {"ชื่อข้อหา": "x"})

    def test_editing_an_existing_row_writes_over_that_row_only(self):
        svc.upsert("charges", {"ชื่อข้อหา": "ขับรถเร็วเกินกว่าที่กฎหมายกำหนด", "crimeGroup (กลุ่มคดี)": "จราจร/ความเร็ว"})
        self.assertEqual(self._call()["range_name"], "A2:E2")

    def test_a_column_left_out_keeps_its_old_value(self):
        svc.upsert("charges", {"ชื่อข้อหา": "มียาเสพติดไว้ในครอบครอง"})
        self.assertEqual(self._call()["values"][0], ["มียาเสพติดไว้ในครอบครอง", "ยาเสพติด", "DRUG", "", "TRUE"])

    def test_a_new_row_goes_after_the_last_one_with_a_key(self):
        svc.upsert("charges", {"ชื่อข้อหา": "ข้อหาใหม่", "isActive": "TRUE"})
        self.assertEqual(self._call()["range_name"], "A4:E4")

    def test_renaming_onto_an_existing_name_is_refused(self):
        with self.assertRaises(svc.ReferenceTableError):
            svc.upsert("charges", {"ชื่อข้อหา": "มียาเสพติดไว้ในครอบครอง"},
                       original_key="ขับรถเร็วเกินกว่าที่กฎหมายกำหนด")

    def test_editing_a_key_that_does_not_exist_is_refused(self):
        with self.assertRaises(svc.ReferenceTableError):
            svc.upsert("charges", {"ชื่อข้อหา": "ก"}, original_key="ไม่มีข้อหานี้")

    def test_an_empty_key_is_refused(self):
        with self.assertRaises(svc.ReferenceTableError):
            svc.upsert("charges", {"ชื่อข้อหา": "   "})

    def test_deactivating_writes_false_to_the_isactive_cell_only(self):
        svc.set_active("charges", "มียาเสพติดไว้ในครอบครอง", False)
        self.assertEqual(self._call()["range_name"], "E3")
        self.assertEqual(self._call()["values"], [["FALSE"]])

    def test_reactivating_writes_true(self):
        svc.set_active("charges", "มียาเสพติดไว้ในครอบครอง", True)
        self.assertEqual(self._call()["values"], [["TRUE"]])

    def test_report_catalog_has_no_active_column_so_toggling_is_refused(self):
        """ตารางนี้ไม่มี isActive บอกให้ชัดดีกว่าเขียนลงคอลัมน์มั่ว"""
        with self.assertRaises(svc.ReferenceTableError):
            svc.set_active("report-catalog", "RPT_X", False)

    def test_the_charge_dropdown_cache_is_cleared_after_a_write(self):
        """ไม่ล้างแคช เจ้าหน้าที่จะยังเห็นข้อหาเดิมไปอีกห้านาที"""
        svc.reference_service.reset_cache.reset_mock()
        svc.upsert("charges", {"ชื่อข้อหา": "ข้อหาใหม่"})
        svc.reference_service.reset_cache.assert_called_once()


if __name__ == "__main__":
    unittest.main()
