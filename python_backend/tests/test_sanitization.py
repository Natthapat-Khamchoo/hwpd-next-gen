"""
Tests for Formula Injection Sanitization & HTML Escaping (unittest runner compatible)
"""

import unittest
from app.core.sanitization import sanitize_cell_value, sanitize_form_data, escape_html


class TestSanitization(unittest.TestCase):
    def test_sanitize_formula_injection(self):
        self.assertEqual(sanitize_cell_value("=1+1"), "'=1+1")
        self.assertEqual(sanitize_cell_value("+cmd|' /C calc'!A0"), "'+cmd|' /C calc'!A0")
        self.assertEqual(sanitize_cell_value("-100"), "'-100")
        self.assertEqual(sanitize_cell_value("@SUM(A1:A10)"), "'@SUM(A1:A10)")
        self.assertEqual(sanitize_cell_value("Normal Text"), "Normal Text")
        self.assertEqual(sanitize_cell_value(12345), 12345)

    def test_sanitize_recursive_dict(self):
        input_data = {
            "title": "=DANGEROUS",
            "nested": {"val": "+SUM()", "safe": "OK"},
            "items": ["-10", "Safe Item"],
        }

        sanitized = sanitize_form_data(input_data)
        self.assertEqual(sanitized["title"], "'=DANGEROUS")
        self.assertEqual(sanitized["nested"]["val"], "'+SUM()")
        self.assertEqual(sanitized["nested"]["safe"], "OK")
        self.assertEqual(sanitized["items"][0], "'-10")
        self.assertEqual(sanitized["items"][1], "Safe Item")

    def test_escape_html(self):
        self.assertEqual(escape_html("<script>alert('XSS')</script>"), "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;")
        self.assertEqual(escape_html("นาย ก & นาย ข"), "นาย ก &amp; นาย ข")
        self.assertEqual(escape_html(None), "")


if __name__ == "__main__":
    unittest.main()
