"""
แคชระดับตารางต้องลดจำนวนการอ่าน แต่ต้องไม่ทำให้คนเห็นข้อมูลเก่าหลังเขียน

Google ให้อ่าน 60 ครั้ง/นาทีต่อบัญชี และทั้งระบบใช้บัญชีเดียว หน้าคิวของสถานีอ่าน
6 ตารางต่อครั้ง จึงเปิดได้ราว 10 ครั้ง/นาทีทั้งระบบก่อนชนโควตา

อันตรายของแคชคือคนส่งรายงานแล้วไม่เห็นของตัวเองในคิว เลยกดส่งซ้ำ เทสชุดนี้จึงล็อก
ทั้งสองด้าน: ต้องแคชจริง และต้องล้างจริงเมื่อมีการเขียน
"""

import unittest
from unittest import mock

from app.core.schema import get_columns

from app.services import query_service as q

ROWS = [
    ["Sys_RecordID", "x"],
    ["ARR-1", "y"],
]


class TestRowCache(unittest.TestCase):
    def setUp(self):
        q.invalidate_cache()
        self.addCleanup(q.invalidate_cache)
        self.reads = []

        def fake_read(spreadsheet_id, table_name):
            self.reads.append((spreadsheet_id, table_name))
            return [{"_row": 2, q.COL_RECORD_ID: "ARR-1"}]

        patcher = mock.patch.object(q, "read_rows", side_effect=fake_read)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_second_call_within_the_window_does_not_hit_the_sheet(self):
        q.cached_rows("sheet-1", "tb_Arrests")
        q.cached_rows("sheet-1", "tb_Arrests")
        q.cached_rows("sheet-1", "tb_Arrests")
        self.assertEqual(len(self.reads), 1)

    def test_a_different_table_is_cached_separately(self):
        q.cached_rows("sheet-1", "tb_Arrests")
        q.cached_rows("sheet-1", "tb_DailyResult")
        self.assertEqual(len(self.reads), 2)

    def test_a_different_spreadsheet_is_cached_separately(self):
        """แต่ละ กก. คนละสเปรดชีต ห้ามให้ กก.1 เห็นข้อมูลของ กก.2"""
        q.cached_rows("sheet-1", "tb_Arrests")
        q.cached_rows("sheet-2", "tb_Arrests")
        self.assertEqual(len(self.reads), 2)

    def test_the_entry_expires(self):
        q.cached_rows("sheet-1", "tb_Arrests")
        with mock.patch.object(q.time, "time", return_value=q.time.time() + q._ROW_CACHE_TTL_SECONDS + 1):
            q.cached_rows("sheet-1", "tb_Arrests")
        self.assertEqual(len(self.reads), 2)

    def test_writing_clears_that_table_so_the_sender_sees_their_own_row(self):
        q.cached_rows("sheet-1", "tb_Arrests")
        q.invalidate_cache("sheet-1", "tb_Arrests")
        q.cached_rows("sheet-1", "tb_Arrests")
        self.assertEqual(len(self.reads), 2)

    def test_clearing_one_table_leaves_the_others_cached(self):
        q.cached_rows("sheet-1", "tb_Arrests")
        q.cached_rows("sheet-1", "tb_DailyResult")
        q.invalidate_cache("sheet-1", "tb_Arrests")
        q.cached_rows("sheet-1", "tb_DailyResult")
        self.assertEqual(self.reads.count(("sheet-1", "tb_DailyResult")), 1)

    def test_find_record_never_uses_the_cache(self):
        """
        find_record คืน _row ที่ approve/cancel เอาไปเขียนต่อ เลขแถวจากแคชที่เลื่อนแล้ว
        จะกลายเป็นเขียนทับรายการของคนอื่น
        """
        import inspect
        source = inspect.getsource(q.find_record)
        self.assertIn("read_rows(", source)
        self.assertNotIn("cached_rows(", source)


if __name__ == "__main__":
    unittest.main()


class TestSingleFlight(unittest.TestCase):
    """
    คำขอที่ต้องการตารางเดียวกันพร้อมกันต้องอ่าน Sheets จริงแค่ครั้งเดียว

    แคช TTL อย่างเดียวไม่พอ เพราะหน้าหนึ่งยิงหลายคำขอพร้อมกัน ทุกตัวพลาดแคชพร้อมกัน
    แล้ววิ่งไปอ่านพร้อมกัน ชนเพดาน 60 ครั้ง/นาทีของ Google จน backoff วนเกือบ 100
    วินาทีแล้วตอบ 502 — หน้าเว็บค้างรอทั้งนั้น เคยเกิดขึ้นจริงบน production
    """

    def test_concurrent_readers_trigger_one_read(self):
        import threading
        import time

        calls = []

        def slow_read(spreadsheet_id, table_name):
            calls.append(table_name)
            time.sleep(0.2)
            return [get_columns("tb_DailyResult")]

        q.invalidate_cache()
        with mock.patch.object(q.sheets_service, "read_table", side_effect=slow_read):
            threads = [
                threading.Thread(target=q.cached_rows, args=("db", "tb_DailyResult"))
                for _ in range(8)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        q.invalidate_cache()

        self.assertEqual(len(calls), 1, "8 คำขอพร้อมกันต้องอ่าน Sheets จริงครั้งเดียว")

    def test_different_tables_are_not_serialised_behind_one_lock(self):
        # ล็อกต้องแยกรายตาราง ไม่งั้นการอ่านตาราง A ไปบล็อกตาราง B โดยไม่จำเป็น
        import threading

        started = threading.Event()
        release = threading.Event()

        def blocking_read(spreadsheet_id, table_name):
            if table_name == "tb_DailyResult":
                started.set()
                release.wait(timeout=2)
            return [get_columns(table_name)]

        q.invalidate_cache()
        with mock.patch.object(q.sheets_service, "read_table", side_effect=blocking_read):
            slow = threading.Thread(target=q.cached_rows, args=("db", "tb_DailyResult"))
            slow.start()
            self.assertTrue(started.wait(timeout=2))
            # ตารางอื่นต้องอ่านได้ทันทีระหว่างที่ตัวแรกยังค้างอยู่
            q.cached_rows("db", "tb_Arrests")
            release.set()
            slow.join(timeout=3)
        q.invalidate_cache()
