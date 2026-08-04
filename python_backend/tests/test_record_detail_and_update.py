"""
ตรวจรายละเอียดก่อนอนุมัติ (ข้อ 9) และแก้ไขรายการของตัวเอง (ข้อ 10)

เทสที่สำคัญที่สุดคือชุด `TestUpdateGuards` — ฟีเจอร์แก้ไขเปิดทางให้เขียนทับข้อมูล
ที่ผ่านการตรวจแล้วได้ ถ้ากันไม่ครบ เจ้าหน้าที่จะแก้ยอดหลังอนุมัติหรือย้ายรายงาน
ข้ามสถานีได้โดยไม่มีใครเห็น
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("SESSION_SECRET", "test-secret-for-record-tests")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import create_session_token  # noqa: E402
from app import main  # noqa: E402
from app.services import query_service  # noqa: E402

FAKE_ROUTER = '{"5":{"OPS":"sheet-div-5"}}'

OWNER = {"username": "test51", "role": "Unit_Staff", "station": "51"}
ADMIN = {"username": "adm51", "role": "Station_Admin", "station": "51"}


def arrest_record(status=query_service.STATUS_PENDING, action_by="test51"):
    return {
        "_row": 7,
        "_spreadsheetId": "sheet-div-5",
        query_service.COL_RECORD_ID: "ARR-1",
        query_service.COL_TIMESTAMP: "2026-08-01T09:00:00",
        query_service.COL_LAST_UPDATE: "2026-08-01T09:00:00",
        query_service.COL_ACTION_BY: action_by,
        query_service.COL_STATUS: status,
        query_service.COL_IS_ACTIVE: "TRUE",
        query_service.COL_ACTUAL_DATE: "2026-08-01",
        query_service.COL_STATION_ID: "51",
        query_service.COL_UNIT_ID: "สามเงา",
        "หัวข้อการจับกุม": "จับกุมยาเสพติด",
        "สถานที่จับกุม": "ทล.1 กม.571",
        "ละติจูด": "16.8",
        "ลองจิจูด": "98.5",
        "Attachment_Folder": "https://drive.google.com/folder/abc",
        "เลขคดี": "",
    }


class RecordTestCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(main.app, raise_server_exceptions=False)

    def token(self, user):
        return {"x-token": create_session_token(user)}


class TestRecordDetail(RecordTestCase):
    """ข้อ 9 — แอดมินต้องเห็นเนื้อรายงานครบก่อนกดอนุมัติ"""

    def detail(self, user=ADMIN, record=None):
        row = record or arrest_record()
        with mock.patch.object(query_service, "find_record", return_value=row):
            return self.client.get(
                "/api/records/detail",
                params={"sheetName": "tb_Arrests", "recordId": "ARR-1"},
                headers=self.token(user),
            )

    def test_every_filled_field_comes_back(self):
        data = self.detail().json()["data"]
        labels = [f["label"] for f in data["fields"]]
        self.assertIn("หัวข้อการจับกุม", labels)
        self.assertIn("สถานที่จับกุม", labels)

    def test_blank_fields_are_dropped(self):
        # ตารางจับกุมมี 34 คอลัมน์ ถ้าโชว์ช่องว่างด้วย แอดมินต้องเลื่อนผ่านช่องเปล่า
        # สิบกว่าช่องกว่าจะเจอเนื้อรายงาน ซึ่งทำให้คนเลิกอ่านแล้วกดอนุมัติเลย
        data = self.detail().json()["data"]
        self.assertNotIn("เลขคดี", [f["label"] for f in data["fields"]])

    def test_attachments_are_separated_for_the_ui_to_link(self):
        data = self.detail().json()["data"]
        self.assertEqual(data["attachments"], ["https://drive.google.com/folder/abc"])
        self.assertNotIn("Attachment_Folder", [f["label"] for f in data["fields"]])

    def test_a_folder_placeholder_is_not_treated_as_a_link(self):
        row = arrest_record()
        row["Attachment_Folder"] = "ไม่มีไฟล์แนบ"
        data = self.detail(record=row).json()["data"]
        self.assertEqual(data["attachments"], [])

    def test_the_owner_of_a_pending_record_may_edit(self):
        self.assertTrue(self.detail(user=OWNER).json()["data"]["canEdit"])

    def test_an_admin_looking_at_someone_elses_record_may_not_edit(self):
        # แอดมินอนุมัติหรือตีกลับได้ แต่แก้เนื้อรายงานของคนอื่นไม่ได้ ไม่งั้นชื่อผู้ส่ง
        # จะยังเป็นชื่อเดิมทั้งที่เนื้อหาถูกคนอื่นแก้
        self.assertFalse(self.detail(user=ADMIN).json()["data"]["canEdit"])

    def test_an_approved_record_is_no_longer_editable_by_its_owner(self):
        row = arrest_record(status=query_service.STATUS_APPROVED)
        self.assertFalse(self.detail(user=OWNER, record=row).json()["data"]["canEdit"])

    def test_system_columns_are_not_offered_as_editable(self):
        data = self.detail(user=OWNER).json()["data"]
        for column in (query_service.COL_STATUS, query_service.COL_STATION_ID, query_service.COL_ACTION_BY):
            self.assertNotIn(column, data["editableFields"])


class TestUpdateGuards(RecordTestCase):
    """ข้อ 10 — เปิดทางให้แก้ไขแล้วต้องกันทางที่ใช้แก้ผิดวิธี"""

    def post(self, user, updates, record=None):
        row = record or arrest_record()
        worksheet = mock.Mock()
        with mock.patch.object(query_service, "find_record", return_value=row), \
             mock.patch.object(query_service.sheets_service, "get_worksheet", return_value=worksheet), \
             mock.patch.object(query_service.sheets_service, "with_backoff") as writer, \
             mock.patch.object(query_service, "invalidate_cache"):
            res = self.client.post(
                "/api/records/update",
                json={"sheetName": "tb_Arrests", "recordId": "ARR-1", "updates": updates},
                headers=self.token(user),
            )
        return res, writer

    def test_the_owner_can_change_a_normal_field(self):
        res, writer = self.post(OWNER, {"สถานที่จับกุม": "ทล.1 กม.600"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["changed"], 1)
        self.assertTrue(writer.called)

    def test_editing_leaves_an_audit_entry(self):
        # การแก้ข้อมูลที่รอตรวจอยู่ต้องตามย้อนได้ว่าใครแก้อะไรจากอะไรเป็นอะไร
        _, writer = self.post(OWNER, {"สถานที่จับกุม": "ทล.1 กม.600"})
        written = [call.args for call in writer.call_args_list]
        audit_rows = [args[1] for args in written if args and "append_rows" in str(args[0])]
        self.assertEqual(len(audit_rows), 1)
        entry = audit_rows[0][0]
        self.assertEqual(entry[5], "UPDATE")
        self.assertEqual(entry[7], "ARR-1")
        self.assertIn("ทล.1 กม.571", entry[8])   # ค่าเดิม
        self.assertIn("ทล.1 กม.600", entry[9])   # ค่าใหม่

    def test_someone_elses_record_cannot_be_edited(self):
        res, writer = self.post(ADMIN, {"สถานที่จับกุม": "ทล.1 กม.600"})
        self.assertEqual(res.status_code, 403)
        writer.assert_not_called()

    def test_an_approved_record_cannot_be_edited(self):
        row = arrest_record(status=query_service.STATUS_APPROVED)
        res, writer = self.post(OWNER, {"สถานที่จับกุม": "x"}, record=row)
        self.assertEqual(res.status_code, 409)
        self.assertIn("รออนุมัติ", res.json()["detail"])
        writer.assert_not_called()

    def test_the_status_column_cannot_be_edited(self):
        # ถ้าแก้ได้ เจ้าของรายการจะอนุมัติตัวเองได้
        res, writer = self.post(OWNER, {query_service.COL_STATUS: query_service.STATUS_APPROVED})
        self.assertEqual(res.status_code, 403)
        writer.assert_not_called()

    def test_the_station_column_cannot_be_edited(self):
        # ถ้าแก้ได้ จะย้ายรายงานข้ามสถานีได้
        res, writer = self.post(OWNER, {query_service.COL_STATION_ID: "52"})
        self.assertEqual(res.status_code, 403)
        writer.assert_not_called()

    def test_an_unknown_column_is_rejected(self):
        res, writer = self.post(OWNER, {"ช่องที่ไม่มีจริง": "x"})
        self.assertEqual(res.status_code, 400)
        writer.assert_not_called()

    def test_writing_the_same_value_touches_no_cells(self):
        res, writer = self.post(OWNER, {"สถานที่จับกุม": "ทล.1 กม.571"})
        self.assertEqual(res.json()["changed"], 0)
        writer.assert_not_called()

    def test_an_empty_update_body_is_rejected(self):
        res, _ = self.post(OWNER, {})
        self.assertEqual(res.status_code, 400)


class TestUpdateWritesOnlyChangedCells(RecordTestCase):
    def test_only_the_changed_column_and_the_timestamp_are_written(self):
        """
        เขียนทับทั้งแถวจะกลืนค่าที่คนอื่นเพิ่งแก้ระหว่างที่เราถืออ่านมาค้างไว้
        ซึ่งเป็นอาการที่ชีตไม่มีทางเตือน เพราะไม่มี row lock
        """
        row = arrest_record()
        worksheet = mock.Mock()
        with mock.patch.object(query_service.sheets_service, "get_worksheet", return_value=worksheet), \
             mock.patch.object(query_service.sheets_service, "with_backoff") as writer, \
             mock.patch.object(query_service, "invalidate_cache"):
            query_service.update_record(row, "tb_Arrests", {"สถานที่จับกุม": "ทล.1 กม.600"})

        ranges = writer.call_args.args[1]
        self.assertEqual(len(ranges), 2)   # ช่องที่แก้ + Sys_LastUpdate
        self.assertTrue(all(r["range"].endswith("7") for r in ranges))


if __name__ == "__main__":
    unittest.main()
