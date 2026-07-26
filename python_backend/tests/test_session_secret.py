"""
Tests that SESSION_SECRET has to come from the environment (unittest runner compatible)
"""

import unittest
from unittest import mock

from app.core.config import BURNED_SESSION_SECRETS, get_session_secret
from app.core.security import create_session_token, verify_session_token


class TestSessionSecret(unittest.TestCase):
    def test_missing_secret_raises(self):
        with mock.patch.dict("os.environ", {"SESSION_SECRET": ""}, clear=False):
            with self.assertRaises(RuntimeError):
                get_session_secret()

    def test_leaked_secrets_are_refused(self):
        for burned in BURNED_SESSION_SECRETS:
            with mock.patch.dict("os.environ", {"SESSION_SECRET": burned}, clear=False):
                with self.assertRaises(RuntimeError):
                    get_session_secret()

    def test_configured_secret_is_used(self):
        with mock.patch.dict("os.environ", {"SESSION_SECRET": "a-properly-random-value"}, clear=False):
            self.assertEqual(get_session_secret(), "a-properly-random-value")

    def test_token_round_trip_uses_environment_secret(self):
        user = {"username": "test6", "role": "Unit_Staff", "station": "51"}

        with mock.patch.dict("os.environ", {"SESSION_SECRET": "secret-one"}, clear=False):
            token = create_session_token(user)
            payload = verify_session_token(token)
            self.assertIsNotNone(payload)
            self.assertEqual(payload["s"], "51")

        # A token signed under one secret must not verify under another.
        with mock.patch.dict("os.environ", {"SESSION_SECRET": "secret-two"}, clear=False):
            self.assertIsNone(verify_session_token(token))


if __name__ == "__main__":
    unittest.main()
