"""
/api/health/database ต้องรอดแม้เปิดสเปรดชีตไม่ได้

หน้านี้มีไว้บอกว่ากองไหนต่อฐานข้อมูลไม่ติด ถ้ามันพังไปด้วยเมื่อเจอกองที่พัง
มันก็ไม่มีประโยชน์ในสถานการณ์เดียวที่ต้องใช้มัน — และหน้าผู้บังคับการจะค้าง
"กำลังตรวจสอบ" ตลอดไปโดยไม่มีใครรู้ว่าทำไม

gspread โยน SpreadsheetNotFound / APIError ของตัวเองออกมาตรง ๆ ไม่ผ่านคลาส error
ของโปรเจกต์ ก่อนหน้านี้จึงหลุด except ไปทำให้ตอบ 500 ทั้งหน้า
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("SESSION_SECRET", "test-secret-for-health-tests")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import create_session_token  # noqa: E402
from app import main  # noqa: E402

FAKE_ROUTER = '{"1":{"OPS":"sheet-div-1"},"5":{"OPS":"sheet-div-5"}}'
HQ_ADMIN = {"username": "hqadm", "role": "HQ_Admin", "station": "00"}


class DatabaseHealthTestCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(main.app)
        self.headers = {"x-token": create_session_token(HQ_ADMIN)}

    def _get(self):
        return self.client.get("/api/health/database", headers=self.headers)

    def test_รายงานกองที่เปิดไม่ได้แทนที่จะพังทั้งหน้า(self):
        class SpreadsheetNotFound(Exception):
            """เลียนแบบ gspread.exceptions.SpreadsheetNotFound ที่ไม่ได้สืบทอด error ของเรา"""

        with mock.patch.object(main.sheets_service, "is_configured", return_value=True), \
             mock.patch.object(
                 main.sheets_service, "open_spreadsheet",
                 side_effect=SpreadsheetNotFound("<Response [404]>"),
             ):
            response = self._get()

        self.assertEqual(response.status_code, 200)
        divisions = response.json()["divisions"]
        self.assertEqual(len(divisions), 2)
        for row in divisions:
            self.assertEqual(row["status"], "error")
            self.assertIn("SpreadsheetNotFound", row["message"])

    def test_กองที่ดีอยู่ยังรายงานปกติแม้อีกกองพัง(self):
        class ApiError(Exception):
            pass

        def open_spreadsheet(sheet_id):
            if sheet_id == "sheet-div-1":
                raise ApiError("โควตาเต็ม")
            return mock.Mock(title="ฐานข้อมูล กก.5", worksheets=lambda: [])

        with mock.patch.object(main.sheets_service, "is_configured", return_value=True), \
             mock.patch.object(main.sheets_service, "open_spreadsheet", side_effect=open_spreadsheet):
            response = self._get()

        self.assertEqual(response.status_code, 200)
        rows = {row["division"]: row for row in response.json()["divisions"]}
        self.assertEqual(rows["1"]["status"], "error")
        self.assertEqual(rows["5"]["status"], "ok")
        self.assertEqual(rows["5"]["title"], "ฐานข้อมูล กก.5")

    def test_error_ของ_gspread_ที่หลุดจาก_endpoint_ไหนก็ตอบ_502_พร้อมข้อความ(self):
        """
        รอบก่อนแก้ปัญหานี้เฉพาะ endpoint นี้ แต่ต้นเหตุเป็นของทั้งระบบ — gspread โยน
        error ของตัวเองที่ไม่ได้สืบทอด `SheetWriteError` ทุกเส้นทางจึงจับไม่ติดแล้ว
        กลายเป็น 500 เปล่า ๆ ตอนนี้มีตัวจัดการระดับแอปแปลงเป็น 502 พร้อมข้อความไทย
        """
        from gspread.exceptions import SpreadsheetNotFound

        from app.services import query_service

        client = TestClient(main.app, raise_server_exceptions=False)
        with mock.patch.object(query_service, "cached_rows", side_effect=SpreadsheetNotFound("<Response [404]>")):
            response = client.get("/api/missions?station=51&unit=สามเงา&start=2026-08-01&end=2026-08-05",
                                  headers=self.headers)

        self.assertEqual(response.status_code, 502)
        self.assertIn("Google Sheets", response.json()["message"])

    def test_ต้องมีสิทธิ์ระดับส่วนกลางถึงเรียกได้(self):
        officer = create_session_token({"username": "test51", "role": "Unit_Staff", "station": "51"})
        response = self.client.get("/api/health/database", headers={"x-token": officer})

        self.assertIn(response.status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
