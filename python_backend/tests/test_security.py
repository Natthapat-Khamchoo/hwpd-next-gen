"""
Tests for Password Hashing, Session Verification, and RBAC (unittest runner compatible)
"""

import unittest
from app.core.security import (
    hash_password,
    verify_password,
    create_session_token,
    verify_session_token,
    require_session,
)


class TestSecurity(unittest.TestCase):
    def test_password_hashing_and_verification(self):
        username = "officer51"
        password = "MySecurePassword123"

        hashed = hash_password(username, password)
        self.assertTrue(hashed.startswith("sha256$"))

        # Verify matching password
        self.assertTrue(verify_password(username, password, hashed))

        # Verify wrong password
        self.assertFalse(verify_password(username, "WrongPassword", hashed))

        # Verify username mismatch
        self.assertFalse(verify_password("officer52", password, hashed))

        # Verify legacy plaintext compatibility (Lazy Migration)
        self.assertTrue(verify_password(username, "LegacyPlaintext", "LegacyPlaintext"))

    def test_session_token_lifecycle(self):
        user = {"username": "admin50", "role": "Division_Admin", "station": "50"}
        secret = "test-secret-key-12345"

        token = create_session_token(user, secret=secret, ttl=3600)
        self.assertIsInstance(token, str)
        self.assertIn(".", token)

        # Verify valid token
        payload = verify_session_token(token, secret=secret)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["u"], "admin50")
        self.assertEqual(payload["r"], "Division_Admin")
        self.assertEqual(payload["s"], "50")

        # Verify invalid signature
        self.assertIsNone(verify_session_token(token, secret="wrong-secret"))

    def test_require_session_rbac(self):
        user = {"username": "cmd50", "role": "Division_Commander", "station": "50"}
        secret = "rbac-secret"

        token = create_session_token(user, secret=secret, ttl=3600)

        # Allowed role
        res_ok = require_session(token, allowed_roles=["Division_Commander", "Super_Commander"], secret=secret)
        self.assertEqual(res_ok["status"], "success")

        # Forbidden role
        res_denied = require_session(token, allowed_roles=["HQ_Admin"], secret=secret)
        self.assertEqual(res_denied["status"], "error")
        self.assertIn("ไม่มีสิทธิ์", res_denied["message"])


if __name__ == "__main__":
    unittest.main()
