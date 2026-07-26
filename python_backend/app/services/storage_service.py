"""
HWPD Next Gen - Attachment handling.

The forms send photos as data-URL strings (see filesToBase64 in the frontend).
This module validates and decodes them, then uploads them into a per-report
subfolder of the division's Drive folder, matching the layout Apps Script
produced (`{recordId}_{unitName}` under the division folder).

When no folder is configured for the division, `store_attachments` reports
`stored=False` with a warning instead of pretending the files were kept — a
report whose photos silently vanished is worse than one that says so.
"""

import base64
import binascii
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_division_folder_id

logger = logging.getLogger(__name__)

NO_ATTACHMENT_TEXT = "ไม่มีไฟล์แนบ"

MAX_FILES_PER_REPORT = 10
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB per file, matching typical phone photos
ALLOWED_MIME_PREFIXES = ("image/", "application/pdf")

_DATA_URL_RE = re.compile(r"^data:(?P<mime>[\w.+-]+/[\w.+-]+)?(?:;charset=[\w-]+)?;base64,(?P<payload>.*)$", re.S)
_UNSAFE_NAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


class AttachmentError(ValueError):
    """ไฟล์แนบไม่ผ่านการตรวจสอบ (ชนิด ขนาด หรือรูปแบบข้อมูลไม่ถูกต้อง)"""


def safe_filename(name: str, fallback: str = "attachment") -> str:
    """ตัดอักขระที่ใช้ไต่ path หรือทำให้ชื่อไฟล์เพี้ยนออก"""
    cleaned = _UNSAFE_NAME_CHARS.sub("_", str(name or "")).strip().strip(".")
    cleaned = cleaned.replace("..", "_")
    if not cleaned:
        return fallback
    return cleaned[:120]


def parse_data_url(data: str) -> Tuple[Optional[str], bytes]:
    """
    แยก data-URL (`data:image/jpeg;base64,....`) ออกเป็น (mime, bytes)
    รองรับกรณีที่ส่งมาเป็น base64 เปล่า ๆ โดยไม่มี prefix ด้วย
    """
    raw = str(data or "").strip()
    if not raw:
        raise AttachmentError("ไฟล์แนบไม่มีข้อมูล")

    match = _DATA_URL_RE.match(raw)
    if match:
        mime = match.group("mime")
        payload = match.group("payload")
    else:
        mime = None
        payload = raw

    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AttachmentError("ไฟล์แนบไม่ใช่ข้อมูล base64 ที่ถูกต้อง") from exc

    if not decoded:
        raise AttachmentError("ไฟล์แนบว่างเปล่า")

    return mime, decoded


def validate_attachments(files: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    ตรวจสอบและถอดรหัสไฟล์แนบทั้งชุด คืนรายการ {name, mime, size, content}
    ขว้าง AttachmentError เมื่อข้อมูลไม่ผ่าน เพื่อให้ endpoint ตอบ 400 แทนที่จะทิ้งไฟล์เงียบ ๆ
    """
    if not files:
        return []

    if len(files) > MAX_FILES_PER_REPORT:
        raise AttachmentError(f"แนบไฟล์ได้ไม่เกิน {MAX_FILES_PER_REPORT} ไฟล์ต่อหนึ่งรายงาน")

    decoded_files: List[Dict[str, Any]] = []
    for index, item in enumerate(files, start=1):
        if not isinstance(item, dict):
            raise AttachmentError(f"ไฟล์แนบลำดับที่ {index} มีรูปแบบไม่ถูกต้อง")

        mime, content = parse_data_url(item.get("data", ""))
        mime = (item.get("type") or mime or "").strip().lower()

        if len(content) > MAX_FILE_BYTES:
            raise AttachmentError(
                f"ไฟล์ \"{item.get('name') or index}\" ใหญ่เกิน {MAX_FILE_BYTES // (1024 * 1024)} MB"
            )

        if mime and not mime.startswith(ALLOWED_MIME_PREFIXES):
            raise AttachmentError(f"ไฟล์ \"{item.get('name') or index}\" เป็นชนิดที่ไม่รองรับ ({mime})")

        decoded_files.append(
            {
                "name": safe_filename(item.get("name"), fallback=f"attachment_{index}"),
                "mime": mime or "application/octet-stream",
                "size": len(content),
                "content": content,
            }
        )

    return decoded_files


def drive_service() -> Any:
    """สร้าง Drive API client จาก credentials ชุดเดียวกับที่ใช้เขียน Sheets"""
    from googleapiclient.discovery import build

    from app.services.sheets_service import get_credentials

    return build("drive", "v3", credentials=get_credentials(), cache_discovery=False)


def create_report_folder(service: Any, parent_id: str, folder_name: str) -> Dict[str, str]:
    """สร้างโฟลเดอร์ย่อยของรายงานหนึ่งใบ คืน id และลิงก์"""
    created = (
        service.files()
        .create(
            body={
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            },
            fields="id,webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )
    return {
        "id": created["id"],
        "url": created.get("webViewLink") or f"https://drive.google.com/drive/folders/{created['id']}",
    }


def upload_file(service: Any, folder_id: str, item: Dict[str, Any]) -> str:
    from googleapiclient.http import MediaInMemoryUpload

    media = MediaInMemoryUpload(item["content"], mimetype=item["mime"], resumable=False)
    created = (
        service.files()
        .create(
            body={"name": item["name"], "parents": [folder_id]},
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        )
        .execute()
    )
    return created["id"]


def store_attachments(
    files: Optional[List[Dict[str, Any]]],
    station_id: str,
    record_id: str = "",
    unit_name: str = "",
    folder_id: str = "",
) -> Dict[str, Any]:
    """
    ตรวจสอบไฟล์แนบและอัปโหลดขึ้นโฟลเดอร์ Drive ของ กก. ที่สถานีนั้นสังกัด

    โครงสร้างที่ได้: โฟลเดอร์ กก. / {recordId}_{ชื่อหน่วย} / ไฟล์แนบ
    ตรงกับที่ Apps Script เคยสร้างไว้

    คืนค่า:
      stored     - เก็บไฟล์ได้จริงหรือไม่
      folderUrl  - ข้อความที่จะเขียนลงคอลัมน์ไฟล์แนบและข้อความ LINE
      warning    - ข้อความเตือนสำหรับผู้ใช้ (None ถ้าไม่มีปัญหา)
    """
    decoded = validate_attachments(files)

    if not decoded:
        return {"stored": True, "count": 0, "folderUrl": NO_ATTACHMENT_TEXT, "warning": None}

    parent_id = folder_id or get_division_folder_id(station_id)
    if not parent_id:
        division = str(station_id or "").strip()[:1] or "?"
        logger.warning(
            "รายงาน %s ของสถานี %s มีไฟล์แนบ %d ไฟล์ แต่ กก.%s ยังไม่ได้ตั้งค่าโฟลเดอร์ Drive",
            record_id or "(ยังไม่มีรหัส)", station_id, len(decoded), division,
        )
        return {
            "stored": False,
            "count": len(decoded),
            "folderUrl": f"ยังไม่ได้ตั้งค่าโฟลเดอร์ไฟล์แนบของ กก.{division} ไฟล์ไม่ได้ถูกบันทึก",
            "warning": (
                f"บันทึกข้อมูลแล้ว แต่ไฟล์แนบ {len(decoded)} ไฟล์ยังไม่ได้ถูกจัดเก็บ "
                f"เนื่องจาก กก.{division} ยังไม่ได้ตั้งค่าโฟลเดอร์ Drive กรุณาเก็บไฟล์ต้นฉบับไว้ก่อน"
            ),
        }

    folder_name = "_".join(part for part in [record_id, safe_filename(unit_name, fallback="")] if part) or "attachments"

    try:
        service = drive_service()
        folder = create_report_folder(service, parent_id, folder_name)
        for item in decoded:
            upload_file(service, folder["id"], item)
    except Exception as exc:  # noqa: BLE001 — ต้องไม่ทำให้รายงานที่กรอกมาแล้วหายไป
        logger.error("อัปโหลดไฟล์แนบของ %s ไม่สำเร็จ: %s", record_id, exc)
        return {
            "stored": False,
            "count": len(decoded),
            "folderUrl": "อัปโหลดไฟล์แนบไม่สำเร็จ",
            "warning": (
                f"บันทึกข้อมูลแล้ว แต่อัปโหลดไฟล์แนบ {len(decoded)} ไฟล์ไม่สำเร็จ "
                "กรุณาเก็บไฟล์ต้นฉบับไว้แล้วแจ้งผู้ดูแลระบบ"
            ),
        }

    logger.info("อัปโหลดไฟล์แนบ %d ไฟล์ของ %s ไปที่ %s", len(decoded), record_id, folder["url"])
    return {"stored": True, "count": len(decoded), "folderUrl": folder["url"], "warning": None}
