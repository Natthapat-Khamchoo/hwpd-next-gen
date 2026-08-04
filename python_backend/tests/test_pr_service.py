"""
โมดูลประชาสัมพันธ์ (requirement ข้อ 13)

จุดที่เทสหนักที่สุดคือเกณฑ์คุณภาพสื่อ (BR-01) เพราะเป็นกฎที่ตัดสินว่างานของ
เจ้าหน้าที่จะไปต่อหรือค้างคิว การตีความผิดด้านเดียวก็ทำให้ทั้งระบบใช้ไม่ได้ —
เข้มเกินไปข่าวไม่ผ่านสักใบ หลวมเกินไปเกณฑ์ก็ไม่มีความหมาย
"""

import io
import os
import unittest
from unittest import mock

os.environ.setdefault("SESSION_SECRET", "test-secret-for-pr-tests")

from app.core.schema import get_columns  # noqa: E402
from app.services import pr_service, query_service  # noqa: E402

FAKE_ROUTER = '{"5":{"OPS":"sheet-div-5"}}'

BASE_FORM = {
    "stationId": "51",
    "unitId": "สามเงา",
    "actionBy": "test51",
    "title": "ตำรวจทางหลวงจับกุมขบวนการลักลอบขนสินค้า",
    "content": "เจ้าหน้าที่ตรวจยึดของกลางจำนวนมาก",
    "newsDateTime": "2026-08-04T09:00",
    "newsType": "ผลการจับกุม",
    "source": "internal",
}


def png_bytes(width: int, height: int) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class PRTestCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)


class TestMediaQualityRule(PRTestCase):
    """BR-01 — ด้านสั้นต้องไม่ต่ำกว่า 1080 พิกเซล"""

    def test_landscape_full_hd_passes(self):
        self.assertTrue(pr_service.check_dimensions(1920, 1080)[0])

    def test_portrait_full_hd_also_passes(self):
        # สื่อจากมือถือเป็นแนวตั้ง (1080x1920) การเช็คแค่ความสูงจะตกภาพแนวนอนที่ถูกต้อง
        # ส่วนการเช็คแค่ความกว้างจะตกภาพแนวตั้ง จึงต้องวัดด้านสั้น
        self.assertTrue(pr_service.check_dimensions(1080, 1920)[0])

    def test_below_the_bar_fails_with_a_readable_reason(self):
        passed, reason = pr_service.check_dimensions(1280, 720)
        self.assertFalse(passed)
        self.assertIn("1280x720", reason)
        self.assertIn("1080p", reason)

    def test_exactly_at_the_bar_passes(self):
        self.assertTrue(pr_service.check_dimensions(1080, 1080)[0])

    def test_unreadable_dimensions_fail_rather_than_pass(self):
        # จุดประสงค์ของเกณฑ์คือให้คนมาดูของที่ระบบไม่มั่นใจ การปล่อยผ่านสิ่งที่วัดไม่ได้
        # ทำให้เกณฑ์นี้ไม่มีความหมาย
        for bad in (None, "", "ไม่ทราบ", 0, -5):
            self.assertFalse(pr_service.check_dimensions(bad, 1080)[0], repr(bad))


class TestBackendRecheck(PRTestCase):
    """ค่าจากเบราว์เซอร์แก้ได้ด้วย DevTools จึงต้องตรวจซ้ำฝั่ง backend"""

    def test_pillow_reading_overrides_what_the_browser_claimed(self):
        media = pr_service.evaluate_media([
            {"name": "fake.png", "type": "image/png", "width": 1920, "height": 1080,
             "_bytes": png_bytes(640, 480)},
        ])
        self.assertEqual((media[0]["width"], media[0]["height"]), (640, 480))
        self.assertFalse(media[0]["passed"])
        self.assertEqual(media[0]["checkedBy"], "backend(Pillow)")

    def test_a_genuinely_large_image_still_passes_the_recheck(self):
        media = pr_service.evaluate_media([
            {"name": "real.png", "type": "image/png", "width": 1920, "height": 1080,
             "_bytes": png_bytes(1920, 1080)},
        ])
        self.assertTrue(media[0]["passed"])

    def test_video_falls_back_to_the_browser_value(self):
        # Render แผนฟรีไม่มี ffprobe จึงตรวจวิดีโอซ้ำฝั่ง backend ไม่ได้
        media = pr_service.evaluate_media([
            {"name": "clip.mp4", "type": "video/mp4", "width": 1920, "height": 1080},
        ])
        self.assertTrue(media[0]["passed"])
        self.assertEqual(media[0]["checkedBy"], "browser")

    def test_a_corrupt_image_is_flagged_not_crashed_on(self):
        media = pr_service.evaluate_media([
            {"name": "broken.png", "type": "image/png", "width": 1920, "height": 1080,
             "_bytes": b"not an image at all"},
        ])
        # อ่านไม่ได้ก็ตกกลับไปใช้ค่าจากเบราว์เซอร์ ไม่ใช่ทำให้ทั้งคำขอล้ม
        self.assertEqual(media[0]["checkedBy"], "browser")


class TestNewsRow(PRTestCase):
    def build(self, media=None, matched=None, **overrides):
        return pr_service.prepare_news(
            dict(BASE_FORM, **overrides), media or [], matched or []
        )

    def test_row_matches_the_schema(self):
        prepared = self.build()
        self.assertEqual(len(prepared["rowData"]), len(get_columns(pr_service.NEWS_TABLE)))

    def test_news_always_starts_pending_regardless_of_media(self):
        # FR-09 — แอดมินเท่านั้นที่อนุมัติ ข่าวจึงเข้าคิวเสมอแม้สื่อผ่านเกณฑ์ครบ
        media = pr_service.evaluate_media([{"name": "a.jpg", "type": "image/jpeg", "width": 1920, "height": 1080}])
        self.assertEqual(self.build(media)["rowData"][4], query_service.STATUS_PENDING)

    def test_low_resolution_media_flags_the_news_for_review(self):
        media = pr_service.evaluate_media([{"name": "small.jpg", "type": "image/jpeg", "width": 640, "height": 480}])
        prepared = self.build(media)
        self.assertTrue(prepared["needsMediaReview"])
        columns = get_columns(pr_service.NEWS_TABLE)
        self.assertEqual(prepared["rowData"][columns.index("ต้องตรวจคุณภาพสื่อ")], "TRUE")
        self.assertIn("small.jpg", prepared["rowData"][columns.index("หมายเหตุการตรวจ")])

    def test_news_without_any_media_is_not_flagged(self):
        self.assertFalse(self.build()["needsMediaReview"])

    def test_a_missing_title_is_rejected(self):
        with self.assertRaises(pr_service.PRError):
            self.build(title="")

    def test_an_unknown_source_is_rejected(self):
        # FR-01 รองรับสามแหล่ง การรับค่าอะไรก็ได้ทำให้ตัวกรองตามแหล่งที่มาไร้ความหมาย
        with self.assertRaises(pr_service.PRError):
            self.build(source="facebook")

    def test_matched_keywords_are_stored_on_the_row(self):
        columns = get_columns(pr_service.NEWS_TABLE)
        prepared = self.build(matched=["ยาเสพติด", "ลักลอบ"])
        self.assertEqual(prepared["rowData"][columns.index("คำค้นที่ตรวจพบ")], "ยาเสพติด, ลักลอบ")


class TestMediaRows(PRTestCase):
    def test_rows_match_the_schema_and_link_back_to_the_news(self):
        media = pr_service.evaluate_media([
            {"name": "a.jpg", "type": "image/jpeg", "width": 1920, "height": 1080},
            {"name": "b.jpg", "type": "image/jpeg", "width": 640, "height": 480},
        ])
        rows = pr_service.prepare_media_rows("PR-1", BASE_FORM, media)
        columns = get_columns(pr_service.MEDIA_TABLE)

        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(len(row), len(columns))
            self.assertEqual(row[columns.index("News_RecordID")], "PR-1")

    def test_failing_media_is_queued_while_passing_media_is_not(self):
        media = pr_service.evaluate_media([
            {"name": "ok.jpg", "type": "image/jpeg", "width": 1920, "height": 1080},
            {"name": "bad.jpg", "type": "image/jpeg", "width": 640, "height": 480},
        ])
        rows = pr_service.prepare_media_rows("PR-1", BASE_FORM, media)
        self.assertEqual(rows[0][4], query_service.STATUS_APPROVED)
        self.assertEqual(rows[1][4], query_service.STATUS_PENDING)


class TestKeywordFiltering(PRTestCase):
    KEYWORDS = [
        {"keyword": "ยาเสพติด", "category": "คดี", "note": "", "isActive": True},
        {"keyword": "ลักลอบ", "category": "คดี", "note": "", "isActive": True},
    ]

    def test_keywords_found_in_the_text_are_returned(self):
        found = pr_service.match_keywords("จับกุมขบวนการลักลอบขนสินค้า", self.KEYWORDS)
        self.assertEqual(found, ["ลักลอบ"])

    def test_matching_ignores_letter_case(self):
        found = pr_service.match_keywords("SCAMMER รายใหญ่", [{"keyword": "scammer", "isActive": True}])
        self.assertEqual(found, ["scammer"])

    def test_empty_text_matches_nothing(self):
        self.assertEqual(pr_service.match_keywords("", self.KEYWORDS), [])

    def test_a_missing_keyword_table_is_treated_as_no_keywords(self):
        # หน่วยที่ยังไม่เคยใช้โมดูลนี้จะยังไม่มีแท็บ ซึ่งไม่ใช่ error
        error = pr_service.sheets_service.SheetWriteError("ไม่พบตาราง tb_PR_Keywords")
        with mock.patch.object(pr_service.sheets_service, "read_table", side_effect=error):
            self.assertEqual(pr_service.get_keywords(), [])


class TestNewsListing(PRTestCase):
    def rows(self):
        def make(record_id, title, source, status, date, active="TRUE", review=""):
            return {
                query_service.COL_RECORD_ID: record_id,
                query_service.COL_TIMESTAMP: f"{date}T09:00:00",
                query_service.COL_STATUS: status,
                query_service.COL_IS_ACTIVE: active,
                query_service.COL_ACTUAL_DATE: date,
                query_service.COL_STATION_ID: "51",
                query_service.COL_UNIT_ID: "สามเงา",
                "หัวข้อข่าว": title,
                "ประเภทข่าว": "ผลการจับกุม",
                "แหล่งที่มา": source,
                "เนื้อหาดิบ": "เนื้อหา",
                "คำค้นที่ตรวจพบ": "",
                "ผู้ส่ง (ยศ ชื่อ สกุล)": "ด.ต. ทดสอบ",
                "ต้องตรวจคุณภาพสื่อ": review,
                "หมายเหตุการตรวจ": "",
                "Attachment_Folder": "",
                "Permalink": "",
            }

        return [
            make("PR-1", "จับกุมยาเสพติด", "internal", query_service.STATUS_PENDING, "2026-08-01", review="TRUE"),
            make("PR-2", "ข่าวจาก CIB", "cib", query_service.STATUS_APPROVED, "2026-08-03"),
            make("PR-3", "ข่าวที่ถูกลบ", "internal", query_service.STATUS_CANCELED, "2026-08-02", active="FALSE"),
        ]

    def list_with(self, **kwargs):
        with mock.patch.object(query_service, "cached_rows", return_value=self.rows()):
            return pr_service.list_news("51", **kwargs)

    def test_soft_deleted_news_never_appears(self):
        # FR-05 บอกให้เก็บถาวร ไม่ใช่ให้แสดงตลอดไป
        self.assertNotIn("PR-3", [i["recordId"] for i in self.list_with()])

    def test_newest_first(self):
        self.assertEqual([i["recordId"] for i in self.list_with()], ["PR-2", "PR-1"])

    def test_filter_by_source(self):
        self.assertEqual([i["recordId"] for i in self.list_with(source="cib")], ["PR-2"])

    def test_filter_by_status(self):
        found = self.list_with(status=query_service.STATUS_PENDING)
        self.assertEqual([i["recordId"] for i in found], ["PR-1"])

    def test_filter_by_needs_review(self):
        self.assertEqual([i["recordId"] for i in self.list_with(only_needs_review=True)], ["PR-1"])

    def test_keyword_search_looks_inside_the_title(self):
        self.assertEqual([i["recordId"] for i in self.list_with(keyword="ยาเสพติด")], ["PR-1"])

    def test_date_range_excludes_rows_outside_it(self):
        found = self.list_with(start="2026-08-03", end="2026-08-31")
        self.assertEqual([i["recordId"] for i in found], ["PR-2"])

    def test_summary_counts_what_the_header_shows(self):
        summary = pr_service.summarize(self.list_with())
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["approved"], 1)
        self.assertEqual(summary["needsMediaReview"], 1)
        self.assertEqual(summary["bySource"], {"internal": 1, "cib": 1})

    def test_export_rows_start_with_a_header(self):
        rows = pr_service.export_rows(self.list_with())
        self.assertEqual(rows[0][0], "รหัสข่าว")
        self.assertEqual(len(rows), 3)   # หัวตาราง + 2 แถว


if __name__ == "__main__":
    unittest.main()
