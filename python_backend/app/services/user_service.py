"""
HWPD Next Gen - User directory service.

อ่านแท็บ `tb_Users` จาก Master Spreadsheet ผ่าน credentials ชุดเดียวกับที่ใช้เขียน
รายงาน (ดู sheets_service) จึงไม่ต้องพึ่งการแชร์ไฟล์แบบสาธารณะอีกต่อไป

ผลลัพธ์ถูกแคชไว้ระยะสั้นเพื่อให้การล็อกอินไม่ต้องยิง Google ทุกครั้ง

คอลัมน์ในชีต: Username, Password, FullName, Station_ID, Unit_ID, Role,
สถานะไปช่วยราชการ, สถานะมาช่วยราชการ, หมายเหตุ, เบอร์โทร, รหัส, ...
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

from app.core.config import MASTER_SHEET_ID
from app.services import sheets_service

logger = logging.getLogger(__name__)

USERS_TABLE = "tb_Users"
CACHE_TTL_SECONDS = 300  # 5 นาที

_cache: Dict[str, Any] = {"users": None, "ts": 0.0}
_lock = threading.Lock()

# ชื่อคอลัมน์ในชีต -> ชื่อฟิลด์ที่ระบบใช้
FIELD_MAP = {
    "Username": "username",
    "Password": "password",
    "FullName": "fullName",
    "Station_ID": "station",
    "Unit_ID": "unit",
    "Role": "role",
    "เบอร์โทร": "phone",
    "รหัส": "code",
    "สถานะไปช่วยราชการ": "secondedOut",
    "สถานะมาช่วยราชการ": "secondedIn",
    "หมายเหตุ": "note",
}


class UserDirectoryUnavailable(RuntimeError):
    """อ่านรายชื่อผู้ใช้จาก Google Sheet ไม่ได้"""


def _parse_rows(rows) -> Dict[str, Dict[str, Any]]:
    if not rows:
        raise UserDirectoryUnavailable(f"ตาราง {USERS_TABLE} ว่างเปล่า")

    header = [str(h).strip() for h in rows[0]]
    positions = {column: header.index(column) for column in FIELD_MAP if column in header}

    missing = [c for c in ("Username", "Password", "Role", "Station_ID") if c not in positions]
    if missing:
        raise UserDirectoryUnavailable(f"ตาราง {USERS_TABLE} ไม่มีคอลัมน์ {', '.join(missing)}")

    users: Dict[str, Dict[str, Any]] = {}
    for row in rows[1:]:
        def cell(column: str) -> str:
            index = positions.get(column)
            if index is None or index >= len(row):
                return ""
            return str(row[index]).strip()

        username = cell("Username")
        if not username:
            continue
        users[username.lower()] = {field: cell(column) for column, field in FIELD_MAP.items()}
        users[username.lower()]["username"] = username

    return users


def get_all_users(force: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    คืนรายชื่อผู้ใช้ทั้งหมด (คีย์เป็น username ตัวพิมพ์เล็ก)
    ขว้าง UserDirectoryUnavailable ถ้าอ่านชีตไม่ได้ เพื่อให้ผู้เรียกแยกได้ว่า
    "รหัสผ่านผิด" กับ "ระบบเข้าถึงรายชื่อผู้ใช้ไม่ได้" คนละเรื่องกัน
    """
    now = time.time()
    cached = _cache.get("users")
    if not force and cached is not None and (now - _cache["ts"]) < CACHE_TTL_SECONDS:
        return cached

    with _lock:
        cached = _cache.get("users")
        if not force and cached is not None and (time.time() - _cache["ts"]) < CACHE_TTL_SECONDS:
            return cached

        try:
            rows = sheets_service.read_table(MASTER_SHEET_ID, USERS_TABLE)
        except sheets_service.SheetNotConfigured as exc:
            raise UserDirectoryUnavailable(str(exc)) from exc
        except sheets_service.SheetWriteError as exc:
            raise UserDirectoryUnavailable(f"อ่านรายชื่อผู้ใช้ไม่สำเร็จ: {exc}") from exc

        users = _parse_rows(rows)
        _cache["users"] = users
        _cache["ts"] = time.time()
        logger.info("โหลดรายชื่อผู้ใช้จาก %s แล้ว %d บัญชี", USERS_TABLE, len(users))
        return users


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """หาผู้ใช้หนึ่งคนตาม username (ไม่สนตัวพิมพ์เล็กใหญ่)"""
    key = (username or "").strip().lower()
    if not key:
        return None
    return get_all_users().get(key)


def reset_cache() -> None:
    """ล้างแคช (ใช้ในเทสและตอนแก้ข้อมูลผู้ใช้ในชีต)"""
    with _lock:
        _cache["users"] = None
        _cache["ts"] = 0.0
