"""
requirement ข้อ 1 — ผู้กำกับการดูสถิติของ กก. อื่นได้ แต่สั่งการ/แก้ไข/อนุมัติไม่ได้

ยิงผ่าน HTTP จริงด้วย TestClient เพราะสิ่งที่ต้องพิสูจน์คือ **สถานะที่ API ตอบกลับ**
ไม่ใช่ค่าที่ฟังก์ชันคืน การเทสระดับฟังก์ชันจะพลาดกรณีที่ endpoint ลืมเรียกตัวตรวจสิทธิ์
ซึ่งเป็นความผิดพลาดที่เกิดง่ายที่สุดเวลาเพิ่ม endpoint ใหม่

การซ่อนปุ่มบนหน้าเว็บไม่ใช่การจำกัดสิทธิ์ ใครก็ยิง API ตรงได้ ไฟล์นี้จึงเทสฝั่ง API
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("SESSION_SECRET", "test-secret-for-rbac-tests")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import create_session_token  # noqa: E402
from app import main  # noqa: E402

FAKE_ROUTER = '{"1":{"OPS":"sheet-div-1"},"5":{"OPS":"sheet-div-5"},"8":{"OPS":"sheet-div-8"}}'

# ผกก. กก.5 — สถานี 50 คือฝ่ายอำนวยการของ กก.5
COMMANDER_5 = {"username": "cmd5", "role": "Division_Commander", "station": "50"}
# ฝอ.กก.5 — ไม่อยู่ในชุดที่ดูข้ามกองได้
HQ_ADMIN_5 = {"username": "hq5", "role": "Division_Admin", "station": "50"}
# ผู้ปฏิบัติ ส.ทล.1 กก.5
OFFICER_51 = {"username": "test51", "role": "Unit_Staff", "station": "51"}


def token(user):
    return create_session_token(user)


class RbacTestCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(main.app, raise_server_exceptions=False)

    def get(self, path, user, **params):
        return self.client.get(path, params=params, headers={"x-token": token(user)})

    def post(self, path, user, payload):
        return self.client.post(path, json=payload, headers={"x-token": token(user)})


class TestCommanderCanReadOtherDivisions(RbacTestCase):
    def test_stats_of_another_division_are_not_forbidden(self):
        # ปล่อยให้ชั้นอ่านชีตล้มได้ (ไม่มี credentials ในเทส) สิ่งที่ตรวจคือ "ไม่ใช่ 403"
        with mock.patch.object(main.hq_service, "executive_overview", return_value={}):
            res = self.get("/api/commander/overview", COMMANDER_5, station="10")
        self.assertNotEqual(res.status_code, 403)

    def test_read_only_flag_is_set_when_looking_at_another_division(self):
        with mock.patch.object(main.hq_service, "executive_overview", return_value={}):
            other = self.get("/api/commander/overview", COMMANDER_5, station="10").json()
            own = self.get("/api/commander/overview", COMMANDER_5, station="50").json()
        self.assertTrue(other["data"]["readOnly"])
        self.assertFalse(own["data"]["readOnly"])

    def test_division_admin_still_cannot_read_other_divisions(self):
        # requirement พูดถึงผู้กำกับการอย่างเดียว ฝ่ายอำนวยการไม่ได้ขอสิทธิ์นี้
        with mock.patch.object(main.hq_service, "executive_overview", return_value={}):
            res = self.get("/api/commander/overview", HQ_ADMIN_5, station="10")
        self.assertEqual(res.status_code, 403)

    def test_an_officer_still_cannot_read_another_station(self):
        res = self.get("/api/daily-summary", OFFICER_51, station="52")
        self.assertEqual(res.status_code, 403)

    def test_the_division_picker_lists_only_configured_divisions(self):
        res = self.get("/api/commander/divisions", COMMANDER_5)
        self.assertEqual(res.status_code, 200)
        listed = res.json()["data"]
        self.assertEqual([d["division"] for d in listed], ["1", "5", "8"])
        self.assertEqual([d["isOwn"] for d in listed], [False, True, False])

    def test_the_division_picker_is_closed_to_roles_without_cross_division_read(self):
        self.assertEqual(self.get("/api/commander/divisions", HQ_ADMIN_5).status_code, 403)
        self.assertEqual(self.get("/api/commander/divisions", OFFICER_51).status_code, 403)


class TestCommanderCannotActOnOtherDivisions(RbacTestCase):
    """
    ครึ่งหลังของข้อ 1 และเป็นครึ่งที่สำคัญกว่า — เปิดสิทธิ์อ่านแล้วต้องไม่เผลอเปิดสิทธิ์เขียนตาม
    """

    def test_sending_an_order_to_another_division_is_forbidden(self):
        res = self.post("/api/commander/order", COMMANDER_5, {"target": "11", "message": "ทดสอบ"})
        self.assertEqual(res.status_code, 403)
        self.assertIn("นอกกองกำกับการ", res.json()["detail"])

    def test_submitting_a_report_into_another_division_is_forbidden(self):
        res = self.post(
            "/api/reports/checkpoint",
            COMMANDER_5,
            {"formData": {"stationId": "11", "unitId": "วังน้อย"}},
        )
        self.assertEqual(res.status_code, 403)

    def test_editing_manpower_of_another_division_is_forbidden(self):
        # tb_Users อยู่ในชีตกลางร่วมกันทุก กก. เดิมค้นด้วย username อย่างเดียวจึงข้ามกองได้
        outsider = {"Username": "u11", "Station_ID": "11", "FullName": "ด.ต. คนของ กก.1", "_row": 2}
        with mock.patch.object(main.hq_service.query_service, "read_rows", return_value=[outsider]), \
             mock.patch.object(main.hq_service.sheets_service, "get_worksheet"):
            res = self.post(
                "/api/hq/manpower/status",
                COMMANDER_5,
                {"username": "u11", "helpStationId": "", "startDate": "", "endDate": "", "remark": ""},
            )
        self.assertEqual(res.status_code, 403)
        self.assertIn("นอกขอบเขต", res.json()["detail"])

    def test_editing_manpower_inside_the_own_division_still_works(self):
        insider = {"Username": "u52", "Station_ID": "52", "FullName": "ด.ต. คนของ กก.5", "_row": 3}
        worksheet = mock.Mock()
        with mock.patch.object(main.hq_service.query_service, "read_rows", return_value=[insider]), \
             mock.patch.object(main.hq_service.sheets_service, "get_worksheet", return_value=worksheet), \
             mock.patch.object(main.hq_service.sheets_service, "with_backoff"), \
             mock.patch.object(main.hq_service.query_service, "invalidate_cache"):
            res = self.post(
                "/api/hq/manpower/status",
                COMMANDER_5,
                {"username": "u52", "helpStationId": "", "startDate": "", "endDate": "", "remark": ""},
            )
        self.assertEqual(res.status_code, 200)

    def test_approving_a_record_reaches_only_the_own_division_database(self):
        # _resolve_record เปิดชีตจากสถานีใน session เสมอ ไม่ใช่จากค่าที่ผู้ใช้ส่งมา
        with mock.patch.object(main.query_service, "find_record") as finder:
            finder.side_effect = main.RecordNotFound("ไม่พบรายการ")
            self.post("/api/records/approve", COMMANDER_5, {"sheetName": "tb_Arrests", "recordId": "ARR-1"})
        self.assertEqual(finder.call_args.args[0], "50")


class TestWriteHelpersStayStrict(unittest.TestCase):
    """
    กันการถอยหลัง — ถ้ามีใครเผลอเอาตัวช่วยฝั่งอ่านไปใช้กับเส้นทางเขียนในอนาคต
    เทสนี้จะไม่จับให้ แต่คอมเมนต์ที่ตัวช่วยกับเทสด้านบนจะเป็นตัวเตือน
    ที่นี่ตรวจว่าตัวช่วยสองตัวยังมีพฤติกรรมต่างกันจริงตามที่ออกแบบไว้
    """

    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_read_helper_lets_a_commander_through(self):
        session = {"u": "cmd5", "r": "Division_Commander", "s": "50"}
        self.assertEqual(main.authorized_station_for_stats("11", session), "11")

    def test_the_write_helper_blocks_the_same_commander(self):
        session = {"u": "cmd5", "r": "Division_Commander", "s": "50"}
        with self.assertRaises(main.HTTPException) as ctx:
            main.authorized_station_id("11", session)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_the_read_helper_still_blocks_an_officer(self):
        session = {"u": "test51", "r": "Unit_Staff", "s": "51"}
        with self.assertRaises(main.HTTPException) as ctx:
            main.authorized_station_for_stats("52", session)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
