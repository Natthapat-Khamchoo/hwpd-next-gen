"""
บัญชีฝ่ายประชาสัมพันธ์ต้องทำได้เฉพาะงานประชาสัมพันธ์

เหตุผลที่ต้องมีเทสชุดนี้: ฝ่าย PR อยู่ระดับ บก. สถานี "00" และ
`check_station_match("00", สถานีอะไรก็ได้)` คืน True เสมอ ด่านขอบเขตสถานีที่
endpoint ฝั่งอ่านส่วนใหญ่ใช้จึงไม่กันบัญชีนี้เลยสักเส้น ถ้าพึ่งแค่การซ่อนเมนู
คนที่เปิด DevTools เป็นจะอ่านรายงานจับกุม ยอดน้ำมัน และกำลังพลของทั้งแปดกองได้

เทสจึงยิงตรงไปที่ endpoint โดยไม่ผ่านหน้าเว็บ ซึ่งเป็นวิธีเดียวที่พิสูจน์ว่าด่านจริง
อยู่ที่ backend ไม่ใช่อยู่ที่การไม่มีปุ่มให้กด
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("SESSION_SECRET", "test-secret-for-pr-only-tests")

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.core.security import create_session_token  # noqa: E402

FAKE_ROUTER = '{"1":{"OPS":"sheet-div-1"},"5":{"OPS":"sheet-div-5"}}'


class PROnlyTestCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(main.app, raise_server_exceptions=False)
        self.pr = {"x-token": create_session_token({"username": "pr01", "role": "PR_Officer", "station": "00"})}
        self.hqadm = {"x-token": create_session_token({"username": "hqadm", "role": "HQ_Admin", "station": "00"})}


class TestWhatThePROfficerCanReach(PROnlyTestCase):
    def test_เส้นทางของงาน_PR_เรียกได้(self):
        for path in ["/api/pr/divisions", "/api/pr/templates", "/api/pr/keywords"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, headers=self.pr).status_code, 200)

    def test_มีสิทธิ์อนุมัติข่าวเหมือนแอดมินคนอื่น(self):
        # ไม่ใช่แค่เข้าถึงได้ แต่ต้องผ่านด่าน _require_pr_admin ด้วย
        # ถ้าตกด่านนั้นจะได้ 403 พร้อมข้อความคนละอันกับด่าน PR_ONLY
        response = self.client.post(
            "/api/pr/news/decide", json={"recordId": "", "approve": True}, headers=self.pr
        )
        self.assertNotEqual(response.status_code, 403)


class TestWhatThePROfficerCannotReach(PROnlyTestCase):
    """ทุกเส้นในนี้ HQ_Admin เรียกได้ แต่ฝ่าย PR ต้องไม่ได้ ทั้งที่อยู่สถานีเดียวกัน"""

    BLOCKED = [
        "/api/national-summary?station=00",
        "/api/division-summary?station=50&start=2026-08-01&end=2026-08-05",
        "/api/hq/manpower?station=50",
        "/api/hq/fuel?station=50&monthYear=2026-08",
        "/api/hq/evidence?station=50",
        "/api/station-pending?station=51",
        "/api/my-pending?username=pr01",
        "/api/map/points?station=50",
        "/api/admin/users",
        "/api/admin/reference/charges",
        "/api/health/database",
        "/api/commander/divisions",
        "/api/commander/overview?station=50",
        "/api/search/national?keyword=x",
        "/api/reports/catalog/exportable",
        "/api/dropdowns/users?station=51",
        "/api/dropdowns/user-phones?station=51",
    ]

    def test_ทุกเส้นทางนอกงาน_PR_ตอบ_403(self):
        for path in self.BLOCKED:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, headers=self.pr).status_code, 403)

    def test_เส้นทางเขียนรายงานปฏิบัติการก็ปิด(self):
        body = {"formData": {"stationId": "51", "unitId": "สามเงา"}, "files": []}
        for path in ["/api/reports/daily", "/api/reports/arrest", "/api/records/approve"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, json=body, headers=self.pr).status_code, 403)

    def test_บทบาทอื่นที่สถานีเดียวกันยังเข้าได้ตามเดิม(self):
        # ยืนยันว่าด่านนี้จับที่บทบาท ไม่ใช่จับที่สถานี "00" — ไม่งั้นจะพังหน้า ฝอ.บก.
        response = self.client.get("/api/commander/divisions", headers=self.hqadm)
        self.assertEqual(response.status_code, 200)


class TestTheAllowlistIsClosedByDefault(PROnlyTestCase):
    """
    เทสสองข้อนี้กวาดทุก route ที่แอปมีจริง แทนที่จะไล่ทีละเส้นด้วยมือ

    จุดประสงค์คือ endpoint ที่เพิ่มวันหลังต้องถูกปิดกับบัญชีนี้โดยปริยาย ถ้าใครเพิ่มเส้น
    ใหม่แล้วมันหลุดเข้ารายการอนุญาตโดยไม่ตั้งใจ เทสนี้จะล้มทันทีโดยไม่ต้องมีใครนึกได้
    """

    def _api_paths(self):
        seen = set()
        for route in main.app.routes:
            path = getattr(route, "path", "")
            if path.startswith("/api/") and "{" not in path and "GET" in getattr(route, "methods", set()):
                seen.add(path)
        return sorted(seen)

    def test_ทุก_GET_ที่ไม่ใช่งาน_PR_ถูกปิดหมด(self):
        # 401 ก็นับว่าปิด — /api/admin/aggregate-status ตรวจโทเคนเองแล้วกันด้วย
        # NATIONAL_VIEW_ROLES จึงตอบ 401 แทน 403 ปลายทางเหมือนกันคือเข้าไม่ได้
        blocked_ok, leaked = 0, []
        for path in self._api_paths():
            if path in main.PR_ONLY_ALLOWED_EXACT or path.startswith(main.PR_ONLY_ALLOWED_PREFIXES):
                continue
            if self.client.get(path, headers=self.pr).status_code in (401, 403):
                blocked_ok += 1
            else:
                leaked.append(path)

        self.assertEqual(leaked, [], f"เส้นทางที่หลุดออกไปให้บัญชี PR: {leaked}")
        self.assertGreater(blocked_ok, 20, "กวาดเจอเส้นทางน้อยเกินไป เทสนี้อาจไม่ได้ตรวจอะไรเลย")

    def test_มี_endpoint_เดียวที่ตรวจโทเคนเองโดยไม่ผ่าน_current_session(self):
        """
        ด่าน PR_ONLY อยู่ใน `current_session` เส้นทางที่ตรวจโทเคนเองจึงข้ามด่านนี้ไปเลย

        ตอนนี้มีเส้นเดียวคือ /api/admin/aggregate-status ซึ่งกันด้วย NATIONAL_VIEW_ROLES
        ของตัวเองอยู่แล้ว แต่ถ้าวันหลังมีคนเขียนเส้นใหม่แบบเดียวกันโดยไม่ได้กันบทบาท
        บัญชี PR จะเข้าถึงได้ทันทีโดยไม่มีอะไรฟ้อง เทสนี้จึงตรึงจำนวนไว้
        """
        import inspect
        import re

        src = inspect.getsource(main)
        bypassing = [
            m.group(2)
            for m in re.finditer(r'@app\.(?:get|post)\("([^"]+)"\)\s*\ndef (\w+)\(([^)]*)\)', src)
            if "current_session" not in m.group(3)
            and "verify_session_token" in src[m.end():m.end() + 900]
        ]
        self.assertEqual(
            bypassing,
            ["aggregate_status"],
            "มี endpoint ที่ตรวจโทเคนเองเพิ่มขึ้น ต้องกันบทบาท PR ที่เส้นนั้นด้วย",
        )

    def test_ทุกเส้นในรายการอนุญาตเป็นงาน_PR_จริง(self):
        # กันกรณี prefix กว้างเกินไปจนลากเส้นที่ไม่เกี่ยวเข้ามาด้วย
        for path in self._api_paths():
            if not (path in main.PR_ONLY_ALLOWED_EXACT or path.startswith(main.PR_ONLY_ALLOWED_PREFIXES)):
                continue
            with self.subTest(path=path):
                self.assertTrue(
                    path.startswith("/api/pr/") or path in main.PR_ONLY_ALLOWED_EXACT,
                    f"{path} อยู่ในรายการอนุญาตแต่ไม่ใช่งาน PR",
                )


if __name__ == "__main__":
    unittest.main()
