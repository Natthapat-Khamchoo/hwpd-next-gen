"""
Tests for how the sheet layer picks its Google credentials (unittest runner compatible).
No network and no gspread import — only the selection logic.
"""

import unittest
from unittest import mock

from app.services import sheets_service

OAUTH_ENV = {
    "GOOGLE_OAUTH_CLIENT_ID": "cid.apps.googleusercontent.com",
    "GOOGLE_OAUTH_CLIENT_SECRET": "csecret",
    "GOOGLE_OAUTH_REFRESH_TOKEN": "1//refresh",
}

BLANK_ENV = {
    "GOOGLE_OAUTH_CLIENT_ID": "",
    "GOOGLE_OAUTH_CLIENT_SECRET": "",
    "GOOGLE_OAUTH_REFRESH_TOKEN": "",
    "GOOGLE_SERVICE_ACCOUNT_JSON": "",
}


def env(**overrides):
    return mock.patch.dict("os.environ", {**BLANK_ENV, **overrides}, clear=False)


class TestAuthModeSelection(unittest.TestCase):
    def test_nothing_configured(self):
        with env():
            self.assertIsNone(sheets_service.auth_mode())
            self.assertFalse(sheets_service.is_configured())

    def test_oauth_when_all_three_present(self):
        with env(**OAUTH_ENV):
            self.assertEqual(sheets_service.auth_mode(), "oauth")
            self.assertTrue(sheets_service.is_configured())

    def test_partial_oauth_is_not_enough(self):
        with env(GOOGLE_OAUTH_CLIENT_ID=OAUTH_ENV["GOOGLE_OAUTH_CLIENT_ID"]):
            self.assertIsNone(sheets_service.auth_mode())

    def test_service_account_when_oauth_absent(self):
        with env(GOOGLE_SERVICE_ACCOUNT_JSON='{"client_email":"bot@x.iam.gserviceaccount.com"}'):
            self.assertEqual(sheets_service.auth_mode(), "service_account")
            self.assertEqual(sheets_service.service_account_email(), "bot@x.iam.gserviceaccount.com")

    def test_oauth_wins_over_service_account(self):
        with env(**OAUTH_ENV, GOOGLE_SERVICE_ACCOUNT_JSON='{"client_email":"bot@x.iam.gserviceaccount.com"}'):
            self.assertEqual(sheets_service.auth_mode(), "oauth")
            # ในโหมด OAuth ไม่ต้องแชร์โฟลเดอร์ให้ใคร จึงไม่ควรแนะนำอีเมล service account
            self.assertIsNone(sheets_service.service_account_email())


class TestNotConfiguredError(unittest.TestCase):
    def test_build_credentials_raises_with_both_options_named(self):
        with env():
            with self.assertRaises(sheets_service.SheetNotConfigured) as ctx:
                sheets_service._build_credentials()
        message = str(ctx.exception)
        self.assertIn("GOOGLE_OAUTH_REFRESH_TOKEN", message)
        self.assertIn("GOOGLE_SERVICE_ACCOUNT_JSON", message)

    def test_malformed_service_account_json_is_reported(self):
        with env(GOOGLE_SERVICE_ACCOUNT_JSON="{not json"):
            with self.assertRaises(sheets_service.SheetNotConfigured):
                sheets_service._load_service_account_info()


if __name__ == "__main__":
    unittest.main()
