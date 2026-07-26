"""
Tests for record ID generation (unittest runner compatible).

พบของจริงตอนทดสอบส่งรายงานจาก 8 กก. พร้อมกัน: รหัสแบบเดิม (ละเอียดถึงนาที + สุ่ม 3 หลัก)
ออกซ้ำกันสองใบ ถ้าเกิดในชีตเดียวกัน การอนุมัติ/ยกเลิกที่อ้างด้วยรหัสจะไปโดนใบผิด
"""

import re
import unittest

from app.services.report_service import generate_record_id

PATTERN = re.compile(r"^(OP|CHK|ARR)-\d{6}-\d{6}-\d{6}$")


class TestGenerateRecordId(unittest.TestCase):
    def test_format_includes_seconds_and_six_random_digits(self):
        record_id = generate_record_id("OP")
        self.assertRegex(record_id, PATTERN)

    def test_prefix_is_preserved(self):
        for prefix in ("OP", "CHK", "ARR"):
            self.assertTrue(generate_record_id(prefix).startswith(f"{prefix}-"))

    def test_ids_generated_back_to_back_are_unique(self):
        # รันในวินาทีเดียวกันเกือบทั้งหมด จึงเป็นการทดสอบส่วนสุ่มโดยตรง
        # สุ่ม 6 หลัก 2000 ครั้ง คาดว่าจะชนราว 2 ครั้ง เกณฑ์ 99% จึงหลวมพอไม่ให้เทสวูบวาบ
        count = 2000
        ids = {generate_record_id("CHK") for _ in range(count)}
        self.assertGreaterEqual(len(ids) / count, 0.99, f"ไม่ซ้ำเพียง {len(ids)}/{count}")

    def test_random_suffix_is_zero_padded(self):
        suffixes = [generate_record_id("OP").rsplit("-", 1)[1] for _ in range(50)]
        self.assertTrue(all(len(s) == 6 for s in suffixes), suffixes)


if __name__ == "__main__":
    unittest.main()
