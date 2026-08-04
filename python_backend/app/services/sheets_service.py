"""
HWPD Next Gen - Google Sheets persistence.

This is the layer that was missing: `prepare_*` in report_service builds a row,
and this module is what actually puts it in the division's spreadsheet.

Two ways to authenticate, checked in this order:

1. **OAuth user credentials** — GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET
   and GOOGLE_OAUTH_REFRESH_TOKEN. The API acts as the person who granted consent,
   so the sheets stay owned by them and no extra sharing is needed. Use this when
   an organization policy blocks service-account key creation
   (`iam.disableServiceAccountKeyCreation`). Get the refresh token with
   `python scripts/get_oauth_token.py`.
2. **Service account** — GOOGLE_SERVICE_ACCOUNT_JSON, holding either the raw key
   JSON (convenient as a Render environment variable) or a path to the key file.
   The folder has to be shared with the service account's own address.

Without either, every write raises SheetNotConfigured and the API turns that into
a clear message rather than accepting a report it cannot store.

gspread is imported lazily so `python -m unittest` still runs with nothing installed.
"""

import json
import logging
import os
import random
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core import config as _config  # noqa: F401 — importing this loads .env
from app.core.schema import get_columns

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client_lock = threading.Lock()
_client: Any = None

# Sheets API allows 60 reads/minute/user. Looking the worksheet up on every append
# burns two reads per report, so the handle is cached per (spreadsheet, table).
_worksheet_cache: Dict[Tuple[str, str], Any] = {}
_worksheet_lock = threading.Lock()

RETRY_STATUSES = (429, 500, 502, 503)
MAX_ATTEMPTS = 6


class SheetNotConfigured(RuntimeError):
    """ยังไม่ได้ตั้งค่า Service Account จึงเขียนข้อมูลลง Google Sheet ไม่ได้"""


class SheetWriteError(RuntimeError):
    """เขียนข้อมูลลง Google Sheet ไม่สำเร็จ"""


NOT_CONFIGURED_MESSAGE = (
    "ยังไม่ได้ตั้งค่าการเข้าถึง Google Sheets ระบบจึงเขียนข้อมูลไม่ได้ "
    "ตั้ง GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET / GOOGLE_OAUTH_REFRESH_TOKEN "
    "(รับ token ด้วย python scripts/get_oauth_token.py) หรือใช้ GOOGLE_SERVICE_ACCOUNT_JSON "
    "ดูขั้นตอนใน python_backend/README.md"
)


def _oauth_settings() -> Dict[str, str]:
    return {
        "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip(),
        "refresh_token": os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN", "").strip(),
    }


def credentials_source() -> str:
    """คืนค่าดิบของ GOOGLE_SERVICE_ACCOUNT_JSON (ว่าง = ยังไม่ได้ตั้งค่า)"""
    return os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()


def auth_mode() -> Optional[str]:
    """โหมดที่จะใช้เข้าถึง Google: 'oauth', 'service_account' หรือ None ถ้ายังไม่ได้ตั้งค่า"""
    if all(_oauth_settings().values()):
        return "oauth"
    if credentials_source():
        return "service_account"
    return None


def is_configured() -> bool:
    return auth_mode() is not None


def _load_service_account_info() -> Dict[str, Any]:
    """อ่าน service account จาก JSON ตรง ๆ หรือจาก path ที่ชี้ไปยังไฟล์ key"""
    raw = credentials_source()
    if not raw:
        raise SheetNotConfigured(NOT_CONFIGURED_MESSAGE)

    if raw.lstrip().startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SheetNotConfigured(f"GOOGLE_SERVICE_ACCOUNT_JSON ไม่ใช่ JSON ที่ถูกต้อง: {exc}") from exc

    if not os.path.isfile(raw):
        raise SheetNotConfigured(f"ไม่พบไฟล์ Service Account ตามที่ระบุใน GOOGLE_SERVICE_ACCOUNT_JSON: {raw}")

    with open(raw, "r", encoding="utf-8") as handle:
        return json.load(handle)


def service_account_email() -> Optional[str]:
    """
    อีเมลของ Service Account เอาไว้บอกผู้ใช้ว่าต้องแชร์โฟลเดอร์ให้ใคร
    คืน None เมื่อใช้โหมด OAuth เพราะระบบทำงานในนามบัญชีผู้ใช้อยู่แล้ว ไม่ต้องแชร์เพิ่ม
    """
    if auth_mode() != "service_account":
        return None
    try:
        return _load_service_account_info().get("client_email")
    except (SheetNotConfigured, OSError, json.JSONDecodeError):
        return None


def get_credentials() -> Any:
    """คืน credentials ที่ตั้งค่าไว้ ใช้ร่วมกับ Drive API ด้วย"""
    return _build_credentials()


def _build_credentials() -> Any:
    mode = auth_mode()

    if mode == "oauth":
        from google.oauth2.credentials import Credentials as UserCredentials

        settings = _oauth_settings()
        return UserCredentials(
            token=None,
            refresh_token=settings["refresh_token"],
            client_id=settings["client_id"],
            client_secret=settings["client_secret"],
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )

    if mode == "service_account":
        from google.oauth2.service_account import Credentials as ServiceAccountCredentials

        return ServiceAccountCredentials.from_service_account_info(_load_service_account_info(), scopes=SCOPES)

    raise SheetNotConfigured(NOT_CONFIGURED_MESSAGE)


def get_client() -> Any:
    """คืน gspread client (สร้างครั้งเดียวแล้วใช้ซ้ำ)"""
    global _client
    if _client is not None:
        return _client

    with _client_lock:
        if _client is not None:
            return _client
        try:
            import gspread
        except ImportError as exc:
            raise SheetNotConfigured(
                "ยังไม่ได้ติดตั้ง gspread/google-auth (pip install -r requirements.txt)"
            ) from exc

        _client = gspread.authorize(_build_credentials())
        return _client


def reset_client() -> None:
    """ล้าง client และ worksheet ที่แคชไว้ (ใช้ในเทสและตอนเปลี่ยน credential)"""
    global _client
    with _client_lock:
        _client = None
    with _worksheet_lock:
        _worksheet_cache.clear()


def api_status(exc: Exception) -> Optional[int]:
    """ดึง HTTP status ออกจาก APIError ของ gspread"""
    return getattr(getattr(exc, "response", None), "status_code", None)


def with_backoff(operation, *args, **kwargs):
    """
    ลองใหม่เมื่อ Google ตอบ 429 (เกิน quota ต่อนาที) หรือ 5xx ชั่วคราว
    เจอบ่อยเวลาหลายหน่วยส่งรายงานพร้อมกันตอนสิ้นผลัด
    """
    import gspread

    for attempt in range(MAX_ATTEMPTS):
        try:
            return operation(*args, **kwargs)
        except gspread.exceptions.APIError as exc:
            status = api_status(exc)
            if status not in RETRY_STATUSES or attempt == MAX_ATTEMPTS - 1:
                raise
            delay = min(2 ** attempt * 5, 30) + random.uniform(0, 1)
            logger.warning("Google ตอบ %s รอ %.1f วินาทีแล้วลองใหม่ (ครั้งที่ %d)", status, delay, attempt + 1)
            time.sleep(delay)


def open_spreadsheet(spreadsheet_id: str) -> Any:
    """เปิดสเปรดชีตตาม ID พร้อมแปลง error ของ Google ให้เป็นข้อความไทยที่ผู้ใช้แก้ได้"""
    import gspread

    try:
        return with_backoff(get_client().open_by_key, spreadsheet_id)
    except gspread.exceptions.APIError as exc:
        status = api_status(exc)
        if status in (403, 404):
            email = service_account_email()
            how_to_fix = (
                f"กรุณาแชร์ไฟล์/โฟลเดอร์ให้ {email} ในสิทธิ์ Editor แล้วลองใหม่"
                if email
                else "ตรวจว่าบัญชีที่ให้ consent ตอนสร้าง refresh token มีสิทธิ์แก้ไขไฟล์นี้จริง"
            )
            raise SheetWriteError(f"เข้าถึงสเปรดชีต {spreadsheet_id} ไม่ได้ {how_to_fix}") from exc
        raise SheetWriteError(f"Google Sheets API ตอบกลับผิดพลาด: {exc}") from exc


def ensure_worksheet(spreadsheet: Any, table_name: str) -> Any:
    """
    คืนแท็บของตารางที่ต้องการ ถ้ายังไม่มีให้สร้างพร้อมหัวคอลัมน์
    ทำให้สเปรดชีตเปล่า ๆ ใช้งานได้ทันทีโดยไม่ต้องตั้งค่าด้วยมือก่อน
    """
    import gspread

    columns = get_columns(table_name)

    try:
        worksheet = with_backoff(spreadsheet.worksheet, table_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = with_backoff(
            spreadsheet.add_worksheet, title=table_name, rows=1000, cols=max(len(columns), 26)
        )
        with_backoff(worksheet.update, range_name="A1", values=[columns])
        with_backoff(worksheet.freeze, rows=1)
        logger.info("สร้างแท็บ %s พร้อมหัวคอลัมน์ %d ช่อง", table_name, len(columns))
        return worksheet

    if not with_backoff(worksheet.row_values, 1):
        with_backoff(worksheet.update, range_name="A1", values=[columns])
        with_backoff(worksheet.freeze, rows=1)
        logger.info("เติมหัวคอลัมน์ให้แท็บ %s ที่ยังว่างอยู่", table_name)

    return worksheet


def get_worksheet(spreadsheet_id: str, table_name: str, refresh: bool = False, ensure: bool = True) -> Any:
    """
    คืนแท็บที่ต้องการ โดยใช้ handle ที่แคชไว้เพื่อไม่ต้องอ่าน Google ซ้ำทุกครั้งที่บันทึก

    ตั้ง ensure=False สำหรับตารางที่แค่อ่าน (เช่น tb_Users) จะได้ไม่ไปสร้างแท็บ
    หรือเขียนหัวคอลัมน์ทับ เพราะตารางพวกนั้นไม่ได้นิยาม schema ไว้
    """
    key = (spreadsheet_id, table_name)

    if not refresh:
        cached = _worksheet_cache.get(key)
        if cached is not None:
            return cached

    import gspread

    try:
        spreadsheet = open_spreadsheet(spreadsheet_id)
        if ensure:
            worksheet = ensure_worksheet(spreadsheet, table_name)
        else:
            worksheet = with_backoff(spreadsheet.worksheet, table_name)
    except gspread.exceptions.WorksheetNotFound as exc:
        raise SheetWriteError(f"ไม่พบตาราง {table_name} ในสเปรดชีต {spreadsheet_id}") from exc
    except gspread.exceptions.APIError as exc:
        # อย่าปล่อย exception ดิบของ gspread ออกจากชั้นนี้ ไม่งั้น endpoint จะกลายเป็น 500
        raise SheetWriteError(f"เปิดตาราง {table_name} ไม่สำเร็จ: {exc}") from exc

    with _worksheet_lock:
        _worksheet_cache[key] = worksheet
    return worksheet


def read_table(spreadsheet_id: str, table_name: str) -> List[List[str]]:
    """อ่านค่าทั้งแท็บแบบไม่แตะโครงสร้าง คืนลิสต์ของแถว (แถวแรกคือหัวคอลัมน์)"""
    import gspread

    worksheet = get_worksheet(spreadsheet_id, table_name, ensure=False)
    try:
        return with_backoff(worksheet.get_all_values)
    except gspread.exceptions.APIError as exc:
        raise SheetWriteError(f"อ่านตาราง {table_name} ไม่สำเร็จ: {exc}") from exc


def read_tables(spreadsheet_id: str, table_names: List[str]) -> Dict[str, List[List[str]]]:
    """
    อ่านหลายตารางในคำขอเดียวด้วย values.batchGet

    Google คิดโควตาเป็น "จำนวนคำขอ" ไม่ใช่จำนวนข้อมูล การอ่านทีละตารางจึงกินโควตา
    เท่าจำนวนตาราง — หน้าแดชบอร์ดหนึ่งหน้าอ่าน 7-8 ตาราง แปลว่า 8 กก. เปิดพร้อมกัน
    ก็ 60+ คำขอ ชนเพดาน 60 ครั้ง/นาทีทันที (วัดมาแล้ว บางกองรอถึง 80 วินาที)
    รวมเป็นคำขอเดียวจึงลดโควตาที่ใช้ลงเกือบเท่าจำนวนตาราง

    ตารางที่ยังไม่มีแท็บจะไม่อยู่ใน dict ที่คืน ผู้เรียกต้องเผื่อกรณีคีย์หาย
    """
    import gspread

    if not table_names:
        return {}

    spreadsheet = open_spreadsheet(spreadsheet_id)
    existing = {ws.title for ws in with_backoff(spreadsheet.worksheets)}
    wanted = [name for name in table_names if name in existing]
    if not wanted:
        return {}

    try:
        # ใส่ single quote รอบชื่อแท็บเสมอ ชื่อไทยกับชื่อที่มีจุด (tb_HQ_Summary ไม่มี
        # แต่ชื่ออื่นอาจมี) ทำให้ Sheets ตีความ range ผิดถ้าไม่ quote
        ranges = [f"'{name}'" for name in wanted]
        result = with_backoff(spreadsheet.values_batch_get, ranges)
    except gspread.exceptions.APIError as exc:
        raise SheetWriteError(f"อ่านหลายตารางไม่สำเร็จ: {exc}") from exc

    out: Dict[str, List[List[str]]] = {}
    for name, block in zip(wanted, result.get("valueRanges", [])):
        out[name] = block.get("values", []) or []
    return out


def append_report_rows(spreadsheet_id: str, table_name: str, rows: List[List[Any]]) -> Dict[str, Any]:
    """
    เขียนหลายแถวลงตารางเดียวด้วยคำขอเดียว คืน {'spreadsheetId', 'tableName', 'updatedRange'}

    มีไว้สำหรับ audit log ที่หนึ่ง request อาจสร้างหลายรายการ การเรียก append_report_row
    วนลูปจะกิน quota เท่าจำนวนแถว ซึ่งเป็นเพดานที่ระบบนี้ชนอยู่แล้ว
    """
    columns = get_columns(table_name)
    for index, row_data in enumerate(rows):
        if len(row_data) != len(columns):
            raise SheetWriteError(
                f"แถวที่ {index + 1} มีข้อมูล {len(row_data)} ช่อง ไม่ตรงกับหัวคอลัมน์ของ "
                f"{table_name} ({len(columns)} ช่อง)"
            )

    if not rows:
        return {"spreadsheetId": spreadsheet_id, "tableName": table_name, "updatedRange": ""}

    import gspread

    worksheet = get_worksheet(spreadsheet_id, table_name)
    safe_rows = [["" if value is None else value for value in row] for row in rows]

    try:
        result = with_backoff(worksheet.append_rows, safe_rows, value_input_option="RAW")
    except gspread.exceptions.APIError as exc:
        if api_status(exc) in (400, 404):
            logger.warning("handle ของ %s ใช้ไม่ได้แล้ว ดึงใหม่แล้วลองอีกครั้ง", table_name)
            worksheet = get_worksheet(spreadsheet_id, table_name, refresh=True)
            try:
                result = with_backoff(worksheet.append_rows, safe_rows, value_input_option="RAW")
            except gspread.exceptions.APIError as retry_exc:
                raise SheetWriteError(f"บันทึก {len(rows)} แถวลง {table_name} ไม่สำเร็จ: {retry_exc}") from retry_exc
        else:
            raise SheetWriteError(f"บันทึก {len(rows)} แถวลง {table_name} ไม่สำเร็จ: {exc}") from exc

    updated_range = (result or {}).get("updates", {}).get("updatedRange", "")
    logger.info("บันทึก %d แถวลง %s แล้ว (%s)", len(rows), table_name, updated_range or "ไม่ทราบตำแหน่ง")

    return {"spreadsheetId": spreadsheet_id, "tableName": table_name, "updatedRange": updated_range}


def append_report_row(spreadsheet_id: str, table_name: str, row_data: List[Any]) -> Dict[str, Any]:
    """
    เขียนหนึ่งแถวลงตารางที่กำหนด คืน {'spreadsheetId', 'tableName', 'updatedRange'}
    ขว้าง SheetNotConfigured / SheetWriteError เมื่อทำไม่สำเร็จ
    """
    columns = get_columns(table_name)
    if len(row_data) != len(columns):
        raise SheetWriteError(
            f"จำนวนข้อมูล ({len(row_data)}) ไม่ตรงกับหัวคอลัมน์ของ {table_name} ({len(columns)}) "
            "ตรวจสอบ report_service กับ app/core/schema.py ให้ตรงกัน"
        )

    import gspread

    worksheet = get_worksheet(spreadsheet_id, table_name)

    # ค่า None ทำให้ Sheets API ปฏิเสธทั้งแถว จึงแปลงเป็นสตริงว่างก่อน
    safe_row = ["" if value is None else value for value in row_data]

    # RAW ไม่ใช่ USER_ENTERED เพราะ USER_ENTERED ให้ Sheets ตีความค่าที่ส่งไปใหม่
    # เบอร์โทร "0812345678" จะถูกอ่านเป็นตัวเลขแล้วเลข 0 นำหน้าหายไป (ข้อมูลเก่าที่
    # Apps Script เขียนไว้ก็โดนแบบเดียวกัน) RAW เก็บค่าตามที่ส่งไปเป๊ะ ๆ และยังปิด
    # ช่องโหว่ formula injection ไปในตัว เพราะสตริงที่ขึ้นต้นด้วย = ไม่ถูกคิดเป็นสูตร
    try:
        result = with_backoff(worksheet.append_row, safe_row, value_input_option="RAW")
    except gspread.exceptions.APIError as exc:
        # แท็บอาจถูกลบหรือเปลี่ยนชื่อหลังจากที่แคช handle ไว้ ลองดึงใหม่อีกรอบก่อนยอมแพ้
        if api_status(exc) in (400, 404):
            logger.warning("handle ของ %s ใช้ไม่ได้แล้ว ดึงใหม่แล้วลองอีกครั้ง", table_name)
            worksheet = get_worksheet(spreadsheet_id, table_name, refresh=True)
            try:
                result = with_backoff(worksheet.append_row, safe_row, value_input_option="RAW")
            except gspread.exceptions.APIError as retry_exc:
                raise SheetWriteError(f"บันทึกข้อมูลลง {table_name} ไม่สำเร็จ: {retry_exc}") from retry_exc
        else:
            raise SheetWriteError(f"บันทึกข้อมูลลง {table_name} ไม่สำเร็จ: {exc}") from exc

    updated_range = (result or {}).get("updates", {}).get("updatedRange", "")
    logger.info("บันทึก %s ลง %s แล้ว (%s)", row_data[0], table_name, updated_range or "ไม่ทราบตำแหน่ง")

    return {"spreadsheetId": spreadsheet_id, "tableName": table_name, "updatedRange": updated_range}
