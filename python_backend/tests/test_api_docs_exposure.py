"""
หน้าเอกสาร API ต้องปิดเว้นแต่จะสั่งเปิด

/docs /redoc /openapi.json ของ FastAPI ไม่ต้องล็อกอินและแจง endpoint ทั้งหมดพร้อม
ชื่อฟิลด์ทุกตัว บนเซิร์ฟเวอร์จริงเคยเปิดอยู่และตอบ 200 ให้ทุกคน

เทสไม่ import app ตรง ๆ แต่สร้างใหม่ในแต่ละกรณี เพราะค่าตัวแปรถูกอ่านตอนสร้าง app
ครั้งเดียว การ import แล้วเปลี่ยน env ทีหลังจึงไม่มีผล
"""

import importlib
import os
import sys
import unittest
from unittest import mock


def _build_app(enable_value):
    """สร้าง FastAPI ใหม่ตามค่า ENABLE_API_DOCS ที่กำหนด แล้วคืน set ของ path"""
    env = {"ENABLE_API_DOCS": enable_value} if enable_value is not None else {}
    with mock.patch.dict(os.environ, env, clear=False):
        if enable_value is None:
            os.environ.pop("ENABLE_API_DOCS", None)
        sys.modules.pop("app.main", None)
        module = importlib.import_module("app.main")
        try:
            return {route.path for route in module.app.routes}
        finally:
            sys.modules.pop("app.main", None)


DOC_PATHS = {"/docs", "/redoc", "/openapi.json"}


class TestApiDocsExposure(unittest.TestCase):
    def test_docs_are_closed_when_the_flag_is_absent(self):
        """ค่าเริ่มต้นต้องปิด ลืมตั้งตัวแปรแล้วต้องได้ด้านที่ปลอดภัย ไม่ใช่ด้านที่เปิดโล่ง"""
        paths = _build_app(None)
        self.assertEqual(DOC_PATHS & paths, set())

    def test_docs_stay_closed_for_values_that_are_not_a_clear_yes(self):
        for value in ("", "false", "0", "no", "maybe"):
            with self.subTest(value=value):
                self.assertEqual(DOC_PATHS & _build_app(value), set())

    def test_docs_open_when_explicitly_enabled(self):
        for value in ("true", "TRUE", "1", "yes"):
            with self.subTest(value=value):
                self.assertTrue(DOC_PATHS <= _build_app(value))

    def test_the_real_endpoints_are_unaffected_either_way(self):
        """ปิดเอกสารต้องไม่ไปปิด endpoint ที่ระบบใช้งานจริง"""
        for value in (None, "true"):
            with self.subTest(value=value):
                paths = _build_app(value)
                self.assertIn("/api/login", paths)
                self.assertIn("/api/reports/daily", paths)
                self.assertIn("/api/national-summary", paths)


if __name__ == "__main__":
    unittest.main()
