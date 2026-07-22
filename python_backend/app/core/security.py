"""
HWPD Next Gen - Security & Authentication Engine
Ported from JS (hashPassword_, verifyPassword_, createSessionToken_, requireSession_)
"""

import hmac
import hashlib
import time
import json
import base64
from typing import Dict, Any, List, Optional
from app.core.config import SESSION_SECRET

DEFAULT_PEPPER = "HWPD5_SECURE_PEPPER_2026_V1"
SESSION_TTL_SECONDS = 24 * 3600  # 24 hours


def hash_password(username: str, password: str, pepper: str = DEFAULT_PEPPER) -> str:
    """
    เข้ารหัสผ่านด้วย SHA-256 + Pepper (รูปแบบ sha256$hash)
    เทียบเท่า hashPassword_ ใน JS
    """
    u = str(username or "").strip().lower()
    p = str(password or "")
    combined = f"{u}:{p}:{pepper}".encode("utf-8")
    hashed = hashlib.sha256(combined).hexdigest()
    return f"sha256${hashed}"


def verify_password(username: str, password_input: str, stored_password: str, pepper: str = DEFAULT_PEPPER) -> bool:
    """
    ตรวจสอบรหัสผ่าน รองรับทั้งแบบ SHA-256 Hash และ Plaintext เดิม (สำหรับ Lazy Migration)
    เทียบเท่า verifyPassword_ ใน JS
    """
    if not stored_password:
        return False

    stored_str = str(stored_password).strip()

    # แบบ SHA-256
    if stored_str.startswith("sha256$"):
        expected = hash_password(username, password_input, pepper)
        return hmac.compare_digest(stored_str, expected)

    # แบบ Plaintext เดิม (พร้อมย้ายเข้า SHA-256 ในครั้งถัดไป)
    return stored_str == str(password_input)


def create_session_token(user_data: Dict[str, Any], secret: str = SESSION_SECRET, ttl: int = SESSION_TTL_SECONDS) -> str:
    """
    สร้าง Signed Session Token (HMAC SHA-256)
    เทียบเท่า createSessionToken_ ใน JS
    """
    now = int(time.time())
    payload = {
        "u": user_data.get("username", ""),
        "r": user_data.get("role", ""),
        "s": str(user_data.get("station", "")).strip(),
        "iat": now,
        "exp": now + ttl,
    }

    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")

    signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_session_token(token: str, secret: str = SESSION_SECRET) -> Optional[Dict[str, Any]]:
    """
    ถอดรหัสและตรวจสอบลายเซ็น HMAC ของ Session Token
    เทียบเท่า verifySessionToken_ ใน JS
    """
    if not token or "." not in token:
        return None

    parts = token.split(".")
    if len(parts) != 2:
        return None

    payload_b64, signature = parts[0], parts[1]

    expected_sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
        return None

    try:
        # Re-pad base64
        padded_b64 = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Check expiration
        now = int(time.time())
        if payload.get("exp", 0) < now:
            return None

        return payload
    except Exception:
        return None


def require_session(token: str, allowed_roles: Optional[List[str]] = None, secret: str = SESSION_SECRET) -> Dict[str, Any]:
    """
    ตรวจสอบ Session Token และสิทธิ์การใช้งาน (RBAC)
    เทียบเท่า requireSession_ ใน JS
    """
    session = verify_session_token(token, secret)
    if not session:
        return {"status": "error", "message": "Session หมดอายุหรือไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่"}

    if allowed_roles and session.get("r") not in allowed_roles:
        return {"status": "error", "message": "ไม่มีสิทธิ์ใช้งานฟังก์ชันนี้"}

    return {"status": "success", "session": session}
