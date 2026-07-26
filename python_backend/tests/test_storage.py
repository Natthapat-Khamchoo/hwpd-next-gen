"""
Tests for attachment decoding/validation (unittest runner compatible)
"""

import base64
import unittest
from unittest import mock

from app.services import storage_service
from app.services.storage_service import (
    AttachmentError,
    MAX_FILES_PER_REPORT,
    NO_ATTACHMENT_TEXT,
    parse_data_url,
    safe_filename,
    store_attachments,
    validate_attachments,
)


def data_url(payload: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(payload).decode()


class TestParseDataUrl(unittest.TestCase):
    def test_parses_mime_and_bytes(self):
        mime, content = parse_data_url(data_url(b"hello", "image/jpeg"))
        self.assertEqual(mime, "image/jpeg")
        self.assertEqual(content, b"hello")

    def test_accepts_bare_base64_without_prefix(self):
        mime, content = parse_data_url(base64.b64encode(b"hello").decode())
        self.assertIsNone(mime)
        self.assertEqual(content, b"hello")

    def test_rejects_empty_and_malformed(self):
        with self.assertRaises(AttachmentError):
            parse_data_url("")
        with self.assertRaises(AttachmentError):
            parse_data_url("data:image/png;base64,!!!not-base64!!!")


class TestSafeFilename(unittest.TestCase):
    def test_strips_path_traversal_and_separators(self):
        self.assertNotIn("/", safe_filename("../../etc/passwd"))
        self.assertNotIn("..", safe_filename("../../etc/passwd"))
        self.assertNotIn("\\", safe_filename(r"C:\Windows\evil.png"))

    def test_falls_back_when_name_is_unusable(self):
        self.assertEqual(safe_filename("", fallback="attachment_1"), "attachment_1")
        self.assertEqual(safe_filename("...", fallback="attachment_2"), "attachment_2")


class TestValidateAttachments(unittest.TestCase):
    def test_empty_input_returns_empty_list(self):
        self.assertEqual(validate_attachments(None), [])
        self.assertEqual(validate_attachments([]), [])

    def test_decodes_frontend_payload_shape(self):
        files = [{"name": "photo.jpg", "type": "image/jpeg", "data": data_url(b"abc", "image/jpeg")}]
        decoded = validate_attachments(files)
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0]["name"], "photo.jpg")
        self.assertEqual(decoded[0]["mime"], "image/jpeg")
        self.assertEqual(decoded[0]["size"], 3)
        self.assertEqual(decoded[0]["content"], b"abc")

    def test_rejects_too_many_files(self):
        files = [
            {"name": f"{i}.png", "type": "image/png", "data": data_url(b"x")}
            for i in range(MAX_FILES_PER_REPORT + 1)
        ]
        with self.assertRaises(AttachmentError):
            validate_attachments(files)

    def test_rejects_disallowed_mime(self):
        files = [{"name": "payload.exe", "type": "application/x-msdownload", "data": data_url(b"x")}]
        with self.assertRaises(AttachmentError):
            validate_attachments(files)

    def test_rejects_oversized_file(self):
        with mock.patch("app.services.storage_service.MAX_FILE_BYTES", 4):
            files = [{"name": "big.png", "type": "image/png", "data": data_url(b"12345")}]
            with self.assertRaises(AttachmentError):
                validate_attachments(files)


PHOTO = [{"name": "photo.jpg", "type": "image/jpeg", "data": data_url(b"abc", "image/jpeg")}]


class TestStoreAttachments(unittest.TestCase):
    def test_no_files_is_a_clean_success(self):
        result = store_attachments(None, station_id="51")
        self.assertTrue(result["stored"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["folderUrl"], NO_ATTACHMENT_TEXT)
        self.assertIsNone(result["warning"])

    def test_without_a_division_folder_it_says_files_were_not_kept(self):
        with mock.patch.dict("os.environ", {"DIVISION_FOLDERS_JSON": "{}"}, clear=False):
            result = store_attachments(PHOTO, station_id="51", record_id="ARR-260726-1200-123")

        self.assertFalse(result["stored"])
        self.assertEqual(result["count"], 1)
        self.assertIn("ไฟล์แนบ", result["warning"])
        self.assertIn("กก.5", result["warning"])

    def test_uploads_into_a_per_report_subfolder(self):
        calls = {}

        def fake_create_folder(service, parent_id, folder_name):
            calls["parent"] = parent_id
            calls["name"] = folder_name
            return {"id": "new-folder", "url": "https://drive.google.com/drive/folders/new-folder"}

        def fake_upload(service, folder_id, item):
            calls.setdefault("uploaded", []).append((folder_id, item["name"]))
            return "file-id"

        env = {"DIVISION_FOLDERS_JSON": '{"5":"division-5-folder"}'}
        with mock.patch.dict("os.environ", env, clear=False), mock.patch.object(
            storage_service, "drive_service", return_value=object()
        ), mock.patch.object(storage_service, "create_report_folder", side_effect=fake_create_folder), mock.patch.object(
            storage_service, "upload_file", side_effect=fake_upload
        ):
            result = store_attachments(
                PHOTO, station_id="51", record_id="OP-260726-0800-123", unit_name="หน่วยฯดอนจาน"
            )

        self.assertTrue(result["stored"])
        self.assertIsNone(result["warning"])
        self.assertEqual(result["folderUrl"], "https://drive.google.com/drive/folders/new-folder")
        self.assertEqual(calls["parent"], "division-5-folder")
        self.assertEqual(calls["name"], "OP-260726-0800-123_หน่วยฯดอนจาน")
        self.assertEqual(calls["uploaded"], [("new-folder", "photo.jpg")])

    def test_upload_failure_does_not_lose_the_report(self):
        env = {"DIVISION_FOLDERS_JSON": '{"5":"division-5-folder"}'}
        with mock.patch.dict("os.environ", env, clear=False), mock.patch.object(
            storage_service, "drive_service", side_effect=RuntimeError("Drive ล่ม")
        ):
            result = store_attachments(PHOTO, station_id="51", record_id="OP-260726-0800-123")

        self.assertFalse(result["stored"])
        self.assertEqual(result["count"], 1)
        self.assertIn("อัปโหลดไฟล์แนบ", result["warning"])


if __name__ == "__main__":
    unittest.main()
