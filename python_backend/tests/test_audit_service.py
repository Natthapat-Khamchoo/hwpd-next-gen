"""
ร่องรอยการกระทำ (audit log)

เทสสำคัญที่สุดในไฟล์นี้คือ `TestBufferSurvivesTheMiddlewareBoundary` — บัฟเฟอร์ผูกกับ
ContextVar ซึ่ง endpoint แบบ sync ของ FastAPI ทำงานคนละ thread กับ middleware
ถ้า context ไม่ข้ามไป audit จะเงียบหายโดยไม่มี error ให้เห็นสักตัว
"""

import json
import os
import unittest
from unittest import mock

os.environ.setdefault("SESSION_SECRET", "test-secret-for-audit-tests")

from app.services import audit_service  # noqa: E402

FAKE_ROUTER = '{"5":{"OPS":"sheet-div-5"},"1":{"OPS":"sheet-div-1"}}'

SESSION = {"u": "test51", "r": "Station_Admin", "s": "51"}


class AuditTestCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        audit_service.begin()
        self.addCleanup(audit_service.discard)

    def capture_writes(self):
        """ดัก append_report_rows แล้วคืน mock ไว้ตรวจว่าเขียนอะไรลงไปบ้าง"""
        patcher = mock.patch.object(audit_service.sheets_service, "append_report_rows")
        writer = patcher.start()
        self.addCleanup(patcher.stop)
        return writer


class TestRecordingAndFlushing(AuditTestCase):
    def test_record_does_not_touch_the_sheet_until_flush(self):
        writer = self.capture_writes()
        audit_service.record(SESSION, audit_service.ACTION_APPROVE, "tb_Arrests", "ARR-1")

        writer.assert_not_called()
        self.assertEqual(audit_service.pending(), 1)

        self.assertEqual(audit_service.flush(), 1)
        writer.assert_called_once()
        self.assertEqual(audit_service.pending(), 0)

    def test_several_actions_in_one_request_cost_a_single_api_call(self):
        # เหตุผลทั้งหมดที่มีบัฟเฟอร์คือข้อนี้ ระบบใช้บัญชี Google บัญชีเดียวและชนโควตามาแล้ว
        writer = self.capture_writes()
        for index in range(3):
            audit_service.record(SESSION, audit_service.ACTION_APPROVE, "tb_Arrests", f"ARR-{index}")

        self.assertEqual(audit_service.flush(), 3)
        self.assertEqual(writer.call_count, 1)
        self.assertEqual(len(writer.call_args.args[2]), 3)

    def test_rows_go_to_the_spreadsheet_of_the_station_being_acted_on(self):
        # ฝอ.กก.1 อนุมัติของสถานีในสังกัดตัวเอง log ต้องลงชีตของ กก. ที่รายการนั้นอยู่
        writer = self.capture_writes()
        audit_service.record(SESSION, audit_service.ACTION_APPROVE, "tb_Arrests", "ARR-1", station_id="11")
        audit_service.flush()

        self.assertEqual(writer.call_args.args[0], "sheet-div-1")

    def test_actions_on_two_divisions_split_into_one_call_each(self):
        writer = self.capture_writes()
        audit_service.record(SESSION, audit_service.ACTION_APPROVE, "tb_Arrests", "A", station_id="11")
        audit_service.record(SESSION, audit_service.ACTION_APPROVE, "tb_Arrests", "B", station_id="52")
        audit_service.flush()

        self.assertEqual(writer.call_count, 2)
        self.assertEqual({call.args[0] for call in writer.call_args_list}, {"sheet-div-1", "sheet-div-5"})

    def test_discard_drops_everything_without_writing(self):
        writer = self.capture_writes()
        audit_service.record(SESSION, audit_service.ACTION_CANCEL, "tb_Arrests", "ARR-1")

        self.assertEqual(audit_service.discard(), 1)
        self.assertEqual(audit_service.flush(), 0)
        writer.assert_not_called()

    def test_unknown_action_is_rejected_at_the_call_site(self):
        with self.assertRaises(ValueError) as ctx:
            audit_service.record(SESSION, "Canceled", "tb_Arrests", "ARR-1")
        self.assertIn("APPROVE", str(ctx.exception))

    def test_station_without_a_configured_database_is_skipped_quietly(self):
        writer = self.capture_writes()
        audit_service.record(SESSION, audit_service.ACTION_APPROVE, "tb_Arrests", "X", station_id="31")

        self.assertEqual(audit_service.pending(), 0)
        audit_service.flush()
        writer.assert_not_called()


class TestRowShape(AuditTestCase):
    def build_row(self, **kwargs):
        writer = self.capture_writes()
        audit_service.record(SESSION, audit_service.ACTION_UPDATE, "tb_Arrests", "ARR-9", **kwargs)
        audit_service.flush()
        return writer.call_args.args[2][0]

    def test_row_matches_the_audit_schema_width(self):
        from app.core.schema import get_columns

        self.assertEqual(len(self.build_row()), len(get_columns(audit_service.AUDIT_TABLE)))

    def test_actor_identity_comes_from_the_session_not_the_caller(self):
        row = self.build_row()
        self.assertEqual(row[2], "test51")
        self.assertEqual(row[3], "Station_Admin")
        self.assertEqual(row[4], "51")

    def test_only_changed_fields_are_stored(self):
        before = {"ยอด ว.20": "5", "สถานที่": "กม.10", "_row": 7}
        after = {"ยอด ว.20": "8", "สถานที่": "กม.10", "_row": 7}
        row = self.build_row(before=audit_service.changed_fields(before, after))

        stored = json.loads(row[8])
        self.assertEqual(stored, {"ยอด ว.20": {"from": "5", "to": "8"}})

    def test_empty_diffs_leave_the_cell_blank_rather_than_writing_braces(self):
        self.assertEqual(self.build_row(before={}, after={})[8], "")


class TestChangedFields(unittest.TestCase):
    def test_internal_underscore_fields_are_ignored(self):
        # _row เป็นเลขแถวในชีต ไม่ใช่ข้อมูลของผู้ใช้ และเปลี่ยนได้เองเมื่อมีคนลบแถวอื่น
        diff = audit_service.changed_fields({"_row": 5, "ก": "1"}, {"_row": 9, "ก": "1"})
        self.assertEqual(diff, {})

    def test_added_and_removed_keys_both_show_up(self):
        diff = audit_service.changed_fields({"เก่า": "1"}, {"ใหม่": "2"})
        self.assertEqual(diff["เก่า"], {"from": "1", "to": None})
        self.assertEqual(diff["ใหม่"], {"from": None, "to": "2"})


class TestWriteFailureDoesNotBreakTheRequest(AuditTestCase):
    def test_sheet_error_is_logged_with_the_lost_rows_instead_of_raising(self):
        # ตอน flush รายการหลักถูกบันทึกไปแล้ว ถ้าขว้าง error ตรงนี้ผู้ใช้จะเห็นว่าล้มเหลว
        # ทั้งที่ข้อมูลเข้าไปแล้ว แล้วกดซ้ำจนได้ข้อมูลซ้ำ
        writer = self.capture_writes()
        writer.side_effect = audit_service.sheets_service.SheetWriteError("โควตาเต็ม")
        audit_service.record(SESSION, audit_service.ACTION_APPROVE, "tb_Arrests", "ARR-1")

        with self.assertLogs("app.services.audit_service", level="ERROR") as logs:
            self.assertEqual(audit_service.flush(), 0)

        self.assertIn("ARR-1", logs.output[0])


class TestBufferSurvivesTheMiddlewareBoundary(unittest.TestCase):
    """
    endpoint แบบ `def` (ไม่ใช่ `async def`) ของ FastAPI ทำงานใน threadpool คนละที่กับ
    middleware ที่เปิดบัฟเฟอร์ไว้ ถ้า ContextVar ไม่ข้ามไปด้วย รายการที่ record() ไว้
    ใน endpoint จะหายไปเฉย ๆ ตอน flush โดยไม่มี error ให้เห็น เทสนี้ยิงผ่าน HTTP จริง
    เพื่อพิสูจน์ว่า context ข้ามไปถึง
    """

    def test_entries_recorded_inside_a_sync_endpoint_reach_the_writer(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.main import audit_trail_middleware

        app = FastAPI()
        app.middleware("http")(audit_trail_middleware)

        @app.post("/ok")
        def ok_endpoint():
            audit_service.record(SESSION, audit_service.ACTION_APPROVE, "tb_Arrests", "ARR-SYNC")
            return {"status": "success"}

        @app.post("/fail")
        def failing_endpoint():
            from fastapi import HTTPException

            audit_service.record(SESSION, audit_service.ACTION_APPROVE, "tb_Arrests", "ARR-403")
            raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์")

        with mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False):
            with mock.patch.object(audit_service.sheets_service, "append_report_rows") as writer:
                client = TestClient(app)

                self.assertEqual(client.post("/ok").status_code, 200)
                writer.assert_called_once()
                self.assertEqual(writer.call_args.args[2][0][7], "ARR-SYNC")

                writer.reset_mock()
                # action ที่ถูกปฏิเสธไม่ควรทิ้งร่องรอยว่าเคยสำเร็จ
                self.assertEqual(client.post("/fail").status_code, 403)
                writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
