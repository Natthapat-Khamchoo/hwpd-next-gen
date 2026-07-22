"""
HWPD Next Gen - Security Sanitization Module
Ported from JS (sanitizeFormData_, sanitizeCell_, escapeHtml_)
"""

import html
from typing import Any, Dict, List, Union


def sanitize_cell_value(val: Any) -> Any:
    """
    ป้องกัน Formula Injection (Sheets/Excel Injection)
    หากสตริงขึ้นต้นด้วย =, +, -, @ ให้เติม ' นำหน้า
    เทียบเท่า sanitizeCell_ ใน JS
    """
    if isinstance(val, str):
        trimmed = val.strip()
        if trimmed and trimmed[0] in ("=", "+", "-", "@"):
            return "'" + val
    return val


def sanitize_form_data(data: Any) -> Any:
    """
    วนลูปทำความสะอาดข้อมูลแบบ Recursion ทั้ง Dictionary, List และ String
    เทียบเท่า sanitizeFormData_ ใน JS
    """
    if data is None:
        return None
    if isinstance(data, dict):
        return {k: sanitize_form_data(v) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_form_data(item) for item in data]
    return sanitize_cell_value(data)


def escape_html(val: Any) -> str:
    """
    แปลงอักขระพิเศษสำหรับป้องกัน XSS
    เทียบเท่า escapeHtml_ ใน JS
    """
    if val is None:
        return ""
    return html.escape(str(val))
