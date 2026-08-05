"""
ลิงก์สาธารณะของชิ้นงาน PR (FR-07/08) และรายงานข่าวค้างอนุมัติ (FR-10)

จุดที่เทสหนักที่สุดคือ **ใครสร้างลิงก์ได้ และลิงก์นั้นให้สิทธิ์อะไร** เพราะลิงก์นี้
เปิดได้โดยไม่ต้องล็อกอิน ผิดพลาดครั้งเดียวคือข้อมูลที่ปิดกลับไม่ได้ เอกสาร
`docs/แผนย้ายไปฐานข้อมูลจริง.md` หัวข้อ 8 บันทึกไว้แล้วว่าเคยมีไฟล์ 20 รายการ
ตั้งเป็น "ทุกคนที่มีลิงก์แก้ไขได้" ฟีเจอร์นี้จึงต้องไม่เดินซ้ำรอยเดิม
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("SESSION_SECRET", "test-secret-for-pr-share-tests")

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.core.security import create_session_token  # noqa: E402
from app.services import pr_service, query_service, storage_service  # noqa: E402
from app.services.sheets_service import SheetWriteError  # noqa: E402

FAKE_ROUTER = '{"5":{"OPS":"sheet-div-5"}}'
ADMIN = {"username": "adm51", "role": "Station_Admin", "station": "51"}
OFFICER = {"username": "test51", "role": "Unit_Staff", "station": "51"}


def news_record(status=query_service.STATUS_APPROVED, share_url="", share_id=""):
    return {
        "_row": 7,
        "_spreadsheetId": "sheet-div-5",
        query_service.COL_RECORD_ID: "PR-1",
        query_service.COL_TIMESTAMP: "2026-08-04T09:00:00",
        query_service.COL_STATUS: status,
        query_service.COL_IS_ACTIVE: "TRUE",
        query_service.COL_ACTUAL_DATE: "2026-08-04",
        query_service.COL_STATION_ID: "51",
        query_service.COL_UNIT_ID: "สามเงา",
        "หัวข้อข่าว": "จับกุมขบวนการลักลอบขนสินค้า",
        "ประเภทข่าว": "ผลการจับกุม",
        "แหล่งที่มา": "internal",
        "เนื้อหาดิบ": "เจ้าหน้าที่ตรวจยึดของกลางจำนวนมาก",
        "เนื้อหาที่เรียบเรียงแล้ว": "",
        "คำค้นที่ตรวจพบ": "ลักลอบ",
        "ผู้ส่ง (ยศ ชื่อ สกุล)": "ด.ต. ทดสอบ ระบบ",
        "ต้องตรวจคุณภาพสื่อ": "",
        "หมายเหตุการตรวจ": "",
        "Attachment_Folder": "",
        "เทมเพลตชิ้นงาน PR": "",
        "Share_File_ID": share_id,
        "Share_Url": share_url,
        "วันเวลาที่สร้างลิงก์": "",
    }


class PRShareTestCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(main.app)
        self.admin = {"x-token": create_session_token(ADMIN)}
        self.officer = {"x-token": create_session_token(OFFICER)}
        self.written = {}

        audit = mock.patch.object(main.audit_service, "record")
        audit.start()
        self.addCleanup(audit.stop)

    def with_record(self, record):
        """สลับชั้นที่คุยกับชีตออก แล้วจำค่าที่ระบบสั่งเขียนไว้ตรวจทีหลัง"""
        def write_columns(_record, _table, updates):
            self.written.update(updates)
            return {}

        return (
            mock.patch.object(query_service, "find_record", return_value=record),
            mock.patch.object(query_service, "write_columns", side_effect=write_columns),
        )


class TestStationRouting(PRShareTestCase):
    """
    ข่าวอยู่ในสเปรดชีตของ กก. ไหน ต้องรู้จากรหัสสถานีที่หน้าเว็บส่งมา

    แอดมินส่วนกลางอยู่สถานี "00" ซึ่งไม่ใช่ กก. ไหนเลย ก่อนหน้านี้ทุกเส้นทางยึด
    สถานีจาก session อย่างเดียว งานของแอดมินส่วนกลางจึงล้มทั้งหมดพร้อมข้อความ
    "กองกำกับการ 0 ยังไม่ได้ตั้งค่าฐานข้อมูล" ที่ตามหาต้นเหตุไม่เจอ
    """

    HQ = {"x-token": create_session_token({"username": "hqadm", "role": "HQ_Admin", "station": "00"})}
    #: ผกก. กก.5 — ดูสถิติข้ามกองได้ตาม requirement ข้อ 1 แต่สั่งการข้ามกองไม่ได้
    COMMANDER5 = {"x-token": create_session_token({"username": "cmd5", "role": "Division_Commander", "station": "50"})}

    PATHS = [
        "/api/pr/news/decide",
        "/api/pr/news/compose",
        "/api/pr/news/share",
        "/api/pr/news/share/revoke",
    ]

    def test_แอดมินส่วนกลางทำงานได้เมื่อหน้าเว็บบอกสถานีมาด้วย(self):
        for path in self.PATHS:
            with self.subTest(path=path):
                find, write = self.with_record(news_record(share_url="https://d/f", share_id="file-1"))
                uploaded = {"stored": True, "fileId": "f2", "url": "https://d/f2", "warning": None}
                with find, write, \
                     mock.patch.object(storage_service, "store_public_text", return_value=uploaded), \
                     mock.patch.object(storage_service, "revoke_public_link", return_value={"revoked": True}), \
                     mock.patch.object(query_service, "set_status"):
                    response = self.client.post(
                        path,
                        json={"recordId": "PR-1", "station": "51", "approve": True},
                        headers=self.HQ,
                    )
                self.assertEqual(response.status_code, 200, response.text)

    def test_ค้นข่าวในสเปรดชีตของสถานีที่หน้าเว็บบอกมา_ไม่ใช่ของ_session(self):
        # ถ้ายังยึด session แอดมินส่วนกลางจะไปค้นด้วย "00" ซึ่งไม่ใช่ กก. ไหนเลย
        with mock.patch.object(query_service, "find_record", return_value=news_record()) as find:
            self.client.post(
                "/api/pr/news/compose",
                json={"recordId": "PR-1", "station": "51"},
                headers=self.HQ,
            )
        self.assertEqual(find.call_args.args[0], "51")

    def test_ผกก_สั่งการข้ามกองไม่ได้แม้จะดูสถิติข้ามกองได้(self):
        # requirement ข้อ 1 — ถ้าเผลอใช้ authorized_station_for_stats ตรงนี้ เคสนี้จะผ่าน
        # กลายเป็น ผกก. กก.5 อนุมัติและแจกลิงก์ข่าวของ กก.1 ได้
        for path in self.PATHS:
            with self.subTest(path=path):
                response = self.client.post(
                    path,
                    json={"recordId": "PR-1", "station": "11", "approve": True},
                    headers=self.COMMANDER5,
                )
                self.assertEqual(response.status_code, 403, response.text)

    def test_สิบเวรระบุสถานีอื่นในกองเดียวกันไม่ได้(self):
        response = self.client.post(
            "/api/pr/news/compose",
            json={"recordId": "PR-1", "station": "52"},
            headers=self.admin,
        )
        self.assertEqual(response.status_code, 403)


class TestWhoCanShare(PRShareTestCase):
    def test_ผู้ปฏิบัติทั่วไปสร้างลิงก์สาธารณะไม่ได้(self):
        response = self.client.post(
            "/api/pr/news/share", json={"recordId": "PR-1"}, headers=self.officer
        )
        self.assertEqual(response.status_code, 403)

    def test_ข่าวที่ยังรออนุมัติแจกลิงก์ไม่ได้(self):
        # ถ้าแชร์ก่อนอนุมัติได้ คิวอนุมัติของ FR-09 ก็ข้ามได้ด้วยการกดปุ่มแชร์แทน
        find, write = self.with_record(news_record(status=query_service.STATUS_PENDING))
        with find, write, mock.patch.object(storage_service, "store_public_text") as upload:
            response = self.client.post(
                "/api/pr/news/share", json={"recordId": "PR-1"}, headers=self.admin
            )

        self.assertEqual(response.status_code, 409)
        upload.assert_not_called()

    def test_ข่าวที่ถูกปฏิเสธไปแล้วก็แจกลิงก์ไม่ได้(self):
        find, write = self.with_record(news_record(status=query_service.STATUS_CANCELED))
        with find, write, mock.patch.object(storage_service, "store_public_text") as upload:
            response = self.client.post(
                "/api/pr/news/share", json={"recordId": "PR-1"}, headers=self.admin
            )

        self.assertEqual(response.status_code, 409)
        upload.assert_not_called()

    def test_ข่าวของสถานีอื่นแตะไม่ได้(self):
        other = news_record()
        other[query_service.COL_STATION_ID] = "12"
        find, write = self.with_record(other)
        with find, write:
            response = self.client.post(
                "/api/pr/news/share", json={"recordId": "PR-1"}, headers=self.admin
            )

        self.assertEqual(response.status_code, 403)


class TestSharingAnApprovedNews(PRShareTestCase):
    def share(self, record=None, template="press"):
        find, write = self.with_record(record or news_record())
        uploaded = {"stored": True, "fileId": "file-1", "url": "https://drive/file-1", "warning": None}
        with find, write, \
             mock.patch.object(storage_service, "store_public_text", return_value=uploaded) as upload, \
             mock.patch.object(storage_service, "revoke_public_link", return_value={"revoked": True}) as revoke:
            response = self.client.post(
                "/api/pr/news/share",
                json={"recordId": "PR-1", "template": template},
                headers=self.admin,
            )
        return response, upload, revoke

    def test_คืนลิงก์และเก็บลงชีตครบทุกช่อง(self):
        response, _upload, _revoke = self.share()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["shareUrl"], "https://drive/file-1")
        self.assertEqual(self.written["Share_Url"], "https://drive/file-1")
        self.assertEqual(self.written["Share_File_ID"], "file-1")
        self.assertEqual(self.written["เทมเพลตชิ้นงาน PR"], "press")
        self.assertTrue(self.written["วันเวลาที่สร้างลิงก์"])

    def test_เนื้อหาที่อัปคือชิ้นงานตามเทมเพลตไม่ใช่เนื้อหาดิบเปล่า(self):
        _response, upload, _revoke = self.share(template="facebook")
        text = upload.call_args[0][0]

        self.assertIn("จับกุมขบวนการลักลอบขนสินค้า", text)
        self.assertIn("#ลักลอบ", text)

    def test_ลิงก์เดิมถูกถอนก่อนสร้างลิงก์ใหม่(self):
        # ชิ้นงานรุ่นเก่าที่ยังเปิดได้คือของที่ตามไปปิดไม่ได้อีกเลย
        # เพราะคอลัมน์เก็บรหัสไฟล์ได้ทีละหนึ่ง
        _response, _upload, revoke = self.share(news_record(share_url="https://drive/old", share_id="file-old"))
        revoke.assert_called_once_with("file-old")

    def test_เทมเพลตที่ไม่รู้จักถูกปฏิเสธก่อนแตะ_Drive(self):
        find, write = self.with_record(news_record())
        with find, write, mock.patch.object(storage_service, "store_public_text") as upload:
            response = self.client.post(
                "/api/pr/news/share",
                json={"recordId": "PR-1", "template": "tiktok"},
                headers=self.admin,
            )

        self.assertEqual(response.status_code, 400)
        upload.assert_not_called()

    def test_เขียนชีตพลาดต้องถอนไฟล์ที่เพิ่งอัปทิ้ง(self):
        # ไฟล์ที่เปิดสาธารณะแล้วแต่รหัสไม่ได้ลงชีต = ไฟล์ที่กดถอนจากหน้าเว็บไม่ได้อีกเลย
        uploaded = {"stored": True, "fileId": "file-new", "url": "https://drive/new", "warning": None}
        with mock.patch.object(query_service, "find_record", return_value=news_record(share_id="file-old")), \
             mock.patch.object(query_service, "write_columns", side_effect=SheetWriteError("โควตาเต็ม")), \
             mock.patch.object(storage_service, "store_public_text", return_value=uploaded), \
             mock.patch.object(storage_service, "revoke_public_link", return_value={"revoked": True}) as revoke:
            response = self.client.post(
                "/api/pr/news/share", json={"recordId": "PR-1"}, headers=self.admin
            )

        self.assertEqual(response.status_code, 502)
        revoked = [call.args[0] for call in revoke.call_args_list]
        self.assertIn("file-new", revoked)
        # ลิงก์เดิมที่ชีตยังชี้อยู่ต้องไม่ถูกแตะ ไม่งั้นข่าวใบนี้จะไม่เหลือลิงก์ที่ใช้ได้เลย
        self.assertNotIn("file-old", revoked)

    def test_อัปไม่สำเร็จต้องไม่เขียนลิงก์ปลอมลงชีต(self):
        failed = {"stored": False, "fileId": "", "url": "", "warning": "ยังไม่ได้ตั้งค่าโฟลเดอร์ Drive"}
        find, write = self.with_record(news_record())
        with find, write, mock.patch.object(storage_service, "store_public_text", return_value=failed):
            response = self.client.post(
                "/api/pr/news/share", json={"recordId": "PR-1"}, headers=self.admin
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.written, {})


class TestRevoking(PRShareTestCase):
    def test_ถอนลิงก์แล้วช่องในชีตต้องว่าง(self):
        find, write = self.with_record(news_record(share_url="https://drive/f", share_id="file-1"))
        with find, write, \
             mock.patch.object(storage_service, "revoke_public_link", return_value={"revoked": True}) as revoke:
            response = self.client.post(
                "/api/pr/news/share/revoke", json={"recordId": "PR-1"}, headers=self.admin
            )

        self.assertEqual(response.status_code, 200)
        revoke.assert_called_once_with("file-1")
        self.assertEqual(self.written["Share_Url"], "")
        self.assertEqual(self.written["Share_File_ID"], "")

    def test_ข่าวที่ยังไม่เคยแชร์ตอบว่าไม่มีอะไรให้ถอน(self):
        find, write = self.with_record(news_record())
        with find, write:
            response = self.client.post(
                "/api/pr/news/share/revoke", json={"recordId": "PR-1"}, headers=self.admin
            )

        self.assertEqual(response.status_code, 404)

    def test_ถอนไม่สำเร็จต้องไม่ล้างช่องในชีต(self):
        # ล้างช่องทั้งที่ไฟล์ยังเปิดสาธารณะอยู่ = ลิงก์ลอยที่ไม่มีใครตามไปปิดได้อีก
        find, write = self.with_record(news_record(share_url="https://drive/f", share_id="file-1"))
        failed = {"revoked": False, "warning": "Drive ตอบ 403"}
        with find, write, mock.patch.object(storage_service, "revoke_public_link", return_value=failed):
            response = self.client.post(
                "/api/pr/news/share/revoke", json={"recordId": "PR-1"}, headers=self.admin
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.written, {})


class TestPublicPermissionShape(unittest.TestCase):
    """สิทธิ์ที่ให้กับลิงก์ — reader เท่านั้น ไม่มีกรณีไหนที่ writer มีเหตุผลรองรับ"""

    def test_สิทธิ์ที่ให้คืออ่านอย่างเดียว(self):
        self.assertEqual(storage_service.PUBLIC_PERMISSION, {"type": "anyone", "role": "reader"})

    def test_ให้สิทธิ์ที่ตัวไฟล์ที่ระบุเท่านั้น(self):
        service = mock.MagicMock()
        storage_service.share_publicly(service, "file-1")

        kwargs = service.permissions().create.call_args.kwargs
        self.assertEqual(kwargs["fileId"], "file-1")
        self.assertEqual(kwargs["body"]["role"], "reader")

    def test_ถอนสิทธิ์ลบเฉพาะ_anyone_ไม่แตะสิทธิ์ของคนในหน่วย(self):
        service = mock.MagicMock()
        service.permissions().list().execute.return_value = {
            "permissions": [
                {"id": "p1", "type": "anyone"},
                {"id": "p2", "type": "user"},
            ]
        }
        with mock.patch.object(storage_service, "drive_service", return_value=service):
            result = storage_service.revoke_public_link("file-1")

        self.assertTrue(result["revoked"])
        deleted = [c.kwargs["permissionId"] for c in service.permissions().delete.call_args_list]
        self.assertEqual(deleted, ["p1"])


class TestPendingReportEndpoint(PRShareTestCase):
    """FR-10 — รายงานสำหรับคนที่ต้องไปตามข่าวค้าง ไม่ใช่ตัวเลขสาธารณะ"""

    def test_ผู้ปฏิบัติทั่วไปเปิดรายงานไม่ได้(self):
        response = self.client.get("/api/pr/report/pending", headers=self.officer)
        self.assertEqual(response.status_code, 403)

    def test_แอดมินได้กลุ่มตามสังกัดพร้อมยอดรวม(self):
        report = {"groups": [], "totals": {"pending": 0, "units": 0, "needsMediaReview": 0, "oldestDays": 0}, "aging": []}
        with mock.patch.object(pr_service, "pending_report", return_value=report):
            response = self.client.get("/api/pr/report/pending", headers=self.admin)

        self.assertEqual(response.status_code, 200)
        self.assertIn("groups", response.json()["data"])


if __name__ == "__main__":
    unittest.main()
