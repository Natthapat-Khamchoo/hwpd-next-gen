"""
Tests for the aggregation trigger's shared-secret auth.
No network — nothing here reaches Google.
"""

import unittest
from unittest import mock

from app import main


class TestCronAuthorization(unittest.TestCase):
    def test_rejects_when_no_secret_is_configured(self):
        # ไม่ตั้ง CRON_SECRET = ปิดทางนี้ไปเลย ไม่ใช่เปิดให้ใครก็เรียกได้
        with mock.patch.dict("os.environ", {}, clear=False):
            main.os.environ.pop("CRON_SECRET", None)
            self.assertFalse(main._cron_authorized("อะไรก็ได้"))
            self.assertFalse(main._cron_authorized(""))
            self.assertFalse(main._cron_authorized(None))

    def test_accepts_only_the_exact_secret(self):
        with mock.patch.dict("os.environ", {"CRON_SECRET": "s3cr3t-value"}, clear=False):
            self.assertTrue(main._cron_authorized("s3cr3t-value"))
            self.assertTrue(main._cron_authorized("  s3cr3t-value  "))
            self.assertFalse(main._cron_authorized("s3cr3t-valu"))
            self.assertFalse(main._cron_authorized("S3CR3T-VALUE"))
            self.assertFalse(main._cron_authorized(""))
            self.assertFalse(main._cron_authorized(None))

    def test_blank_configured_secret_does_not_authorize_a_blank_header(self):
        with mock.patch.dict("os.environ", {"CRON_SECRET": "   "}, clear=False):
            self.assertFalse(main._cron_authorized("   "))
            self.assertFalse(main._cron_authorized(""))


class TestAggregateRunsOneAtATime(unittest.TestCase):
    def test_a_second_run_is_skipped_while_one_is_in_flight(self):
        calls = []

        def busy(start, end, divisions=None):
            calls.append((start, end))
            # จำลองรอบที่ยังทำงานอยู่: ล็อกถูกถือไว้ตอน _run_aggregate ถูกเรียกซ้อน
            main._run_aggregate("2026-07-01", "2026-07-07")
            return {}

        with mock.patch.object(main.national_service, "aggregate_national", side_effect=busy):
            main._run_aggregate("2026-07-20", "2026-07-27")

        self.assertEqual(calls, [("2026-07-20", "2026-07-27")])

    def test_the_lock_is_released_even_when_the_run_fails(self):
        with mock.patch.object(
            main.national_service, "aggregate_national", side_effect=RuntimeError("Google ล่ม")
        ):
            main._run_aggregate("2026-07-20", "2026-07-27")

        self.assertTrue(main._aggregate_lock.acquire(blocking=False))
        main._aggregate_lock.release()

    def test_a_failed_run_does_not_propagate_to_the_caller(self):
        with mock.patch.object(
            main.national_service, "aggregate_national", side_effect=RuntimeError("Google ล่ม")
        ):
            main._run_aggregate("2026-07-20", "2026-07-27")   # ต้องไม่ขว้างออกมา


if __name__ == "__main__":
    unittest.main()
