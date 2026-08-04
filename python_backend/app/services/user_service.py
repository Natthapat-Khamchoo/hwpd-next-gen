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
from typing import Any, Dict, List, Optional

from app.core.config import MASTER_SHEET_ID, check_station_match
from app.services import sheets_service

logger = logging.getLogger(__name__)

USERS_TABLE = "tb_Users"
CACHE_TTL_SECONDS = 300  # 5 นาที

# บัญชีประจำหน่วยไม่ใช่คน จึงไม่ควรอยู่ใน dropdown "ผู้รายงาน"
# ตารางนี้ออกแบบไว้ว่า 1 แถว = เจ้าหน้าที่ 1 นาย บัญชีระดับสถานี/กองกำกับที่เพิ่มเข้ามา
# ทีหลังใช้ชื่อหน่วยเป็น FullName จึงต้องมีป้ายแยกให้ชัด ไม่ใช่เดาจากชื่อหรือ Role
UNIT_ACCOUNT_TYPE = "Unit"

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
    "AccountType": "accountType",
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


def is_unit_account(user: Dict[str, Any]) -> bool:
    """บัญชีประจำหน่วย (ชื่อในช่อง FullName เป็นชื่อสถานี ไม่ใช่ชื่อคน)"""
    return str(user.get("accountType") or "").strip().lower() == UNIT_ACCOUNT_TYPE.lower()


def _visible_users(station_id: str, people_only: bool = True) -> List[Dict[str, Any]]:
    """
    ผู้ใช้ที่สถานีนั้นมองเห็นได้ตามลำดับชั้นเดิม (สถานีตรงกัน / ฝอ.กก. เห็นทั้ง กก. /
    ส่วนกลางเห็นทั้งประเทศ) เรียงตามชื่อเพื่อให้ dropdown ไม่สลับตำแหน่งทุกครั้งที่โหลด

    people_only ตัดบัญชีประจำหน่วยออก เพราะช่อง "ผู้รายงาน" ต้องการชื่อคน ไม่ใช่ชื่อสถานี
    """
    requested = str(station_id or "").strip()
    matched = [
        user
        for user in get_all_users().values()
        if user.get("fullName")
        and check_station_match(requested, str(user.get("station") or ""))
        and not (people_only and is_unit_account(user))
    ]
    return sorted(matched, key=lambda user: user["fullName"])


def list_names_for_station(station_id: str) -> List[str]:
    """ชื่อเจ้าหน้าที่สำหรับ dropdown (เทียบเท่า getUserDropdown ใน JS)"""
    return [user["fullName"] for user in _visible_users(station_id)]


def phone_map_for_station(station_id: str) -> Dict[str, str]:
    """ชื่อเจ้าหน้าที่ -> เบอร์โทร (เทียบเท่า getUserPhoneMapping ใน JS)"""
    return {user["fullName"]: user.get("phone", "") for user in _visible_users(station_id)}


# บทบาทที่ถือว่าเป็น "หัวหน้าหน่วยงาน" ของสถานี เรียงตามลำดับความเป็นหัวหน้า
# ใช้ตอบ requirement ข้อ 2 ที่ให้แสดงเบอร์ติดต่อของหัวหน้าหน่วยที่ได้รับคำสั่ง
#
# ชีต tb_Users ไม่มีคอลัมน์ที่บอกตรง ๆ ว่าใครเป็นหัวหน้า มีแต่ Role ซึ่งบอกสิทธิ์
# การใช้งานระบบ **ถ้าหน่วยมีนิยามหัวหน้าที่ต่างจากนี้ แก้ลำดับในลิสต์นี้ที่เดียว**
HEAD_ROLES: List[str] = ["Division_Commander", "Division_Admin", "Station_Admin", "สิบเวร"]


def station_heads(station_id: str) -> List[Dict[str, str]]:
    """
    หัวหน้าหน่วยของสถานีที่ระบุ พร้อมเบอร์โทร เรียงจากตำแหน่งสูงสุดลงมา

    เทียบสถานีแบบตรงตัว ไม่ใช้ check_station_match เพราะที่นี่ต้องการคนของสถานีนั้นจริง ๆ
    ไม่ใช่ทุกคนที่สถานีนั้นมองเห็นได้ (ซึ่งจะลากหัวหน้าของทั้ง กก. เข้ามาด้วย)

    คืนลิสต์ว่างถ้าสถานีนั้นยังไม่มีใครถือบทบาทหัวหน้า ซึ่งเป็นเรื่องข้อมูลไม่ครบ
    ไม่ใช่ error — ผู้เรียกต้องบอกผู้ใช้ตามจริงว่ายังไม่มีเบอร์ติดต่อ
    """
    wanted = str(station_id or "").strip()
    if not wanted:
        return []

    rank = {role: index for index, role in enumerate(HEAD_ROLES)}
    heads = [
        {
            "name": str(user.get("fullName") or ""),
            "role": str(user.get("role") or ""),
            "phone": str(user.get("phone") or ""),
            "station": wanted,
        }
        for user in get_all_users().values()
        if str(user.get("station") or "").strip() == wanted
        and str(user.get("role") or "") in rank
        and user.get("fullName")
        and not is_unit_account(user)
    ]
    heads.sort(key=lambda head: (rank.get(head["role"], len(HEAD_ROLES)), head["name"]))
    return heads


def update_password(username: str, stored_password: str) -> bool:
    """
    เขียนรหัสผ่านใหม่ทับคอลัมน์ Password ของบัญชีนั้น คืน False ถ้าไม่พบ username

    อ่านชีตสดทุกครั้งแทนการใช้แคช เพราะเลขแถวที่แคชไว้อาจเลื่อนไปแล้วถ้ามีคนลบแถว
    ระหว่างนั้น แล้วจะกลายเป็นเขียนทับรหัสผ่านของคนอื่น
    """
    key = (username or "").strip().lower()
    if not key:
        return False

    rows = sheets_service.read_table(MASTER_SHEET_ID, USERS_TABLE)
    if not rows:
        raise UserDirectoryUnavailable(f"ตาราง {USERS_TABLE} ว่างเปล่า")

    header = [str(h).strip() for h in rows[0]]
    for column in ("Username", "Password"):
        if column not in header:
            raise UserDirectoryUnavailable(f"ตาราง {USERS_TABLE} ไม่มีคอลัมน์ {column}")

    name_index = header.index("Username")
    password_column = chr(ord("A") + header.index("Password"))

    for line, row in enumerate(rows[1:], start=2):
        if name_index < len(row) and str(row[name_index]).strip().lower() == key:
            worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, USERS_TABLE, ensure=False)
            sheets_service.with_backoff(
                worksheet.update,
                range_name=f"{password_column}{line}",
                values=[[stored_password]],
                value_input_option="RAW",
            )
            reset_cache()
            logger.info("เปลี่ยนรหัสผ่านของบัญชี %s แล้ว", username)
            return True

    return False


# แก้ได้เฉพาะสองช่องนี้ ชื่อคอลัมน์ในชีต -> ชื่อฟิลด์ที่ API รับ
#
# ตั้งใจไม่ให้แตะ Password, Role, Station_ID, AccountType ผ่านทางนี้ การแก้ Role หรือ
# Station_ID คือการเปลี่ยนสิทธิ์และปลายทางที่รายงานจะถูกเขียนลง ส่วน Password มี
# /api/change-password ที่ hash ให้อยู่แล้ว เขียนตรงจะได้รหัสที่ล็อกอินไม่ได้
EDITABLE_COLUMNS = {"FullName": "fullName", "เบอร์โทร": "phone"}


def update_profile(username: str, fullName: str = None, phone: str = None) -> bool:
    """
    แก้ชื่อจริงและเบอร์โทรของบัญชี คืน False ถ้าไม่พบ username

    อ่านชีตสดเหมือน update_password ด้วยเหตุผลเดียวกัน — เลขแถวที่แคชไว้อาจเลื่อนแล้ว
    ถ้ามีคนเพิ่มหรือลบแถวระหว่างนั้น จะกลายเป็นเขียนทับข้อมูลของคนอื่น

    ส่งเฉพาะช่องที่ต้องการแก้ ช่องที่เป็น None จะไม่ถูกแตะ ไม่ใช่ถูกล้างเป็นค่าว่าง
    """
    key = (username or "").strip().lower()
    if not key:
        return False

    updates_wanted = {"FullName": fullName, "เบอร์โทร": phone}
    updates_wanted = {k: v for k, v in updates_wanted.items() if v is not None}
    if not updates_wanted:
        return False

    rows = sheets_service.read_table(MASTER_SHEET_ID, USERS_TABLE)
    if not rows:
        raise UserDirectoryUnavailable(f"ตาราง {USERS_TABLE} ว่างเปล่า")

    header = [str(h).strip() for h in rows[0]]
    if "Username" not in header:
        raise UserDirectoryUnavailable(f"ตาราง {USERS_TABLE} ไม่มีคอลัมน์ Username")

    missing = [c for c in updates_wanted if c not in header]
    if missing:
        raise UserDirectoryUnavailable(f"ตาราง {USERS_TABLE} ไม่มีคอลัมน์ {', '.join(missing)}")

    name_index = header.index("Username")

    for line, row in enumerate(rows[1:], start=2):
        if name_index < len(row) and str(row[name_index]).strip().lower() == key:
            worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, USERS_TABLE, ensure=False)
            # ส่งเป็นช่วงแยกกันใน batch เดียว เพราะสองคอลัมน์นี้ไม่ได้อยู่ติดกัน
            # (FullName คอลัมน์ C, เบอร์โทร คอลัมน์ J) เขียนเป็นช่วงเดียวจะทับ D-I ทิ้ง
            batch = [
                {"range": f"{chr(ord('A') + header.index(column))}{line}", "values": [[value]]}
                for column, value in updates_wanted.items()
            ]
            sheets_service.with_backoff(worksheet.batch_update, batch, value_input_option="RAW")
            reset_cache()
            logger.info("แก้ข้อมูลบัญชี %s: %s", username, ", ".join(updates_wanted))
            return True

    return False


def reset_cache() -> None:
    """ล้างแคช (ใช้ในเทสและตอนแก้ข้อมูลผู้ใช้ในชีต)"""
    with _lock:
        _cache["users"] = None
        _cache["ts"] = 0.0
