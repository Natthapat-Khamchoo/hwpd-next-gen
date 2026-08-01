"""
ค้นหาเชิงลึกต้องเห็นเฉพาะของที่ผ่านการตรวจแล้ว และต้องไม่พังทั้งคำค้นเพราะ กก. เดียว

ของเดิม (searchStationRecords) กรอง Approved/Active + Sys_IsActive ก่อนเสมอ รายการที่
ยังรออนุมัติหรือถูกยกเลิกไม่ควรไปโผล่ในผลงานของใคร
"""

import unittest
from unittest import mock

from app.services import query_service, search_service

C = query_service


def rec(**kw):
    base = {
        C.COL_RECORD_ID: "ARR-1",
        C.COL_STATUS: C.STATUS_APPROVED,
        C.COL_IS_ACTIVE: True,
        C.COL_ACTUAL_DATE: "2026-07-15",
        C.COL_STATION_ID: "51",
        C.COL_UNIT_ID: "คลองขลุง",
        C.COL_ACTION_BY: "st51",
        "Data_Location": "ด่านตรวจสามเงา",
        "_row": 2,
    }
    base.update(kw)
    return base


class TestSearchDivision(unittest.TestCase):
    def _run(self, rows, keyword="สามเงา", start="", end=""):
        with mock.patch.object(search_service, "get_target_db_id", return_value="sheet-id"), \
             mock.patch.object(query_service, "read_rows",
                               side_effect=lambda _s, table: rows if table == "tb_Arrests" else []):
            return search_service.search_division("51", keyword, start, end)

    def test_finds_a_match_in_any_text_column(self):
        out = self._run([rec()])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["recordId"], "ARR-1")
        self.assertEqual(out[0]["type"], "จับกุมคดีอาญา")

    def test_pending_rows_are_not_returned(self):
        self.assertEqual(self._run([rec(**{C.COL_STATUS: C.STATUS_PENDING})]), [])

    def test_canceled_rows_are_not_returned(self):
        self.assertEqual(self._run([rec(**{C.COL_STATUS: C.STATUS_CANCELED})]), [])

    def test_deactivated_rows_are_not_returned(self):
        self.assertEqual(self._run([rec(**{C.COL_IS_ACTIVE: False})]), [])

    def test_rows_outside_the_date_range_are_not_returned(self):
        self.assertEqual(self._run([rec()], start="2026-08-01", end="2026-08-31"), [])
        self.assertEqual(len(self._run([rec()], start="2026-07-01", end="2026-07-31")), 1)

    def test_system_status_columns_are_not_searchable(self):
        """พิมพ์ 'approved' ต้องไม่ได้ทุกแถวในระบบกลับมา"""
        self.assertEqual(self._run([rec()], keyword="approved"), [])

    def test_search_is_case_insensitive(self):
        self.assertEqual(len(self._run([rec(Data_Location="Checkpoint ALPHA")], keyword="alpha")), 1)

    def test_an_empty_keyword_returns_nothing_rather_than_everything(self):
        self.assertEqual(self._run([rec()], keyword="   "), [])


class TestSearchNational(unittest.TestCase):
    def test_one_unreadable_division_does_not_sink_the_whole_search(self):
        def fake(station_id, *_a):
            if station_id == "30":
                raise RuntimeError("เปิดสเปรดชีตไม่ได้")
            return [{"recordId": f"R-{station_id}", "date": "2026-07-15"}]

        with mock.patch.object(search_service, "get_db_router",
                               return_value={str(d): {"OPS": f"id{d}"} for d in range(1, 5)}), \
             mock.patch.object(search_service, "search_division", side_effect=fake):
            out = search_service.search_national("อะไรก็ได้", "", "")

        self.assertEqual({r["recordId"] for r in out}, {"R-10", "R-20", "R-40"})
        self.assertTrue(all("divName" in r for r in out))

    def test_division_zero_is_skipped(self):
        """บก.ทล. ส่วนกลางไม่มีสถานีปฏิบัติการของตัวเอง"""
        seen = []
        with mock.patch.object(search_service, "get_db_router",
                               return_value={"0": {"OPS": "x"}, "1": {"OPS": "y"}}), \
             mock.patch.object(search_service, "search_division",
                               side_effect=lambda s, *_a: seen.append(s) or []):
            search_service.search_national("คำ", "", "")
        self.assertEqual(seen, ["10"])


if __name__ == "__main__":
    unittest.main()
