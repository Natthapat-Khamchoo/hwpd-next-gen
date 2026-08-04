"""
HWPD Next Gen - โมดูลประชาสัมพันธ์ (requirement ข้อ 13)

รอบนี้ทำแกนหลักห้าส่วน — FR-01 รับข่าว, FR-02 กรองคำค้นและตรวจคุณภาพสื่อ,
FR-04 ตารางรวมข่าว, FR-05 เก็บถาวรแบบ soft delete พร้อม audit, FR-09 สิทธิ์อนุมัติ

ส่วนที่ยังไม่ทำในรอบนี้ (แจ้งไว้ในแผนหัวข้อ 6): FR-03 ตั้งเวลาเผยแพร่จริง,
FR-06 AI เกลาข้อความ, FR-07/08 สร้างลิงก์แชร์, FR-10 รายงานสรุป
คอลัมน์ `Post_ID` / `Permalink` / `วันเวลาที่เผยแพร่` เว้นไว้รอ FR-03 แล้ว

**เกณฑ์คุณภาพสื่อ (BR-01)** ต่ำกว่า 1080p ไม่ได้แปลว่าปฏิเสธ แต่แปลว่าเข้าคิวรอ
พิจารณา ข่าวจึงถูกบันทึกเสมอ ไม่ทิ้งงานของเจ้าหน้าที่เพราะภาพความละเอียดต่ำ
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import MASTER_SHEET_ID, get_target_db_id
from app.core.sanitization import sanitize_form_data
from app.services import query_service, sheets_service
from app.services.report_service import generate_record_id

logger = logging.getLogger(__name__)

NEWS_TABLE = "tb_PR_News"
MEDIA_TABLE = "tb_PR_Media"
KEYWORDS_TABLE = "tb_PR_Keywords"

# เกณฑ์ตาม BR-01 — ด้านสั้นของภาพ/วิดีโอต้องไม่ต่ำกว่า 1080 พิกเซล
#
# วัดด้วยด้านสั้น ไม่ใช่ความสูง เพราะสื่อแนวตั้งที่ถ่ายจากมือถือ (1080x1920) ผ่านเกณฑ์
# เหมือนแนวนอน (1920x1080) การเช็ค height >= 1080 อย่างเดียวจะตกภาพแนวนอนที่ถูกต้อง
MIN_SHORT_EDGE = 1080

# แหล่งที่มาที่รองรับ (FR-01)
SOURCE_INTERNAL = "internal"
KNOWN_SOURCES = frozenset({SOURCE_INTERNAL, "cib", "hwpd"})

STATUS_PENDING = query_service.STATUS_PENDING
STATUS_APPROVED = query_service.STATUS_APPROVED


class PRError(RuntimeError):
    """ข้อมูลข่าวไม่ถูกต้อง"""


# --------------------------------------------------------------- คำค้นของแอดมิน


def get_keywords(active_only: bool = True) -> List[Dict[str, str]]:
    """
    คำค้นที่แอดมินตั้งไว้ (FR-02) อ่านจากชีตกลาง ใช้ร่วมกันทุก กก.

    ตารางยังไม่มีในชีตของหน่วยที่ยังไม่ได้ใช้โมดูลนี้ ซึ่งไม่ใช่ error — ถือว่ายังไม่มี
    คำค้น แล้วข่าวทุกใบจะผ่านการกรองไปตามปกติ
    """
    try:
        rows = sheets_service.read_table(MASTER_SHEET_ID, KEYWORDS_TABLE)
    except sheets_service.SheetWriteError as exc:
        if "ไม่พบตาราง" in str(exc):
            return []
        raise

    keywords: List[Dict[str, str]] = []
    for row in rows[1:]:
        word = str(row[0]).strip() if row else ""
        if not word:
            continue
        is_active = str(row[3]).strip().upper() if len(row) > 3 else ""
        if active_only and is_active == "FALSE":
            continue
        keywords.append(
            {
                "keyword": word,
                "category": str(row[1]).strip() if len(row) > 1 else "",
                "note": str(row[2]).strip() if len(row) > 2 else "",
                "isActive": is_active != "FALSE",
            }
        )
    return keywords


def match_keywords(text: str, keywords: Optional[List[Dict[str, str]]] = None) -> List[str]:
    """คำค้นที่พบในเนื้อข่าว เทียบแบบไม่สนตัวพิมพ์เล็กใหญ่"""
    haystack = str(text or "").lower()
    if not haystack:
        return []
    words = keywords if keywords is not None else get_keywords()
    return [k["keyword"] for k in words if k["keyword"].lower() in haystack]


# ----------------------------------------------------------- ตรวจคุณภาพสื่อ (BR-01)


def check_dimensions(width: Any, height: Any) -> Tuple[bool, str]:
    """
    ผ่านเกณฑ์ 1080p หรือไม่ คืน (ผ่าน, เหตุผลที่ไม่ผ่าน)

    ขนาดที่อ่านไม่ได้ถือว่า **ไม่ผ่าน** ไม่ใช่ผ่าน เพราะจุดประสงค์ของเกณฑ์คือให้คนมาดู
    ของที่ระบบไม่มั่นใจ การปล่อยผ่านสิ่งที่วัดไม่ได้ทำให้เกณฑ์นี้ไม่มีความหมาย
    """
    try:
        w, h = int(width), int(height)
    except (TypeError, ValueError):
        return False, "อ่านขนาดไฟล์ไม่ได้ ต้องให้เจ้าหน้าที่ตรวจเอง"

    if w <= 0 or h <= 0:
        return False, "อ่านขนาดไฟล์ไม่ได้ ต้องให้เจ้าหน้าที่ตรวจเอง"

    short_edge = min(w, h)
    if short_edge < MIN_SHORT_EDGE:
        return False, f"ความละเอียด {w}x{h} ต่ำกว่าเกณฑ์ {MIN_SHORT_EDGE}p"
    return True, ""


def inspect_image_bytes(content: bytes) -> Tuple[int, int]:
    """
    อ่านขนาดภาพจริงฝั่ง backend ด้วย Pillow คืน (0, 0) ถ้าอ่านไม่ได้

    ตรวจซ้ำจากที่เบราว์เซอร์ส่งมาเพราะค่าที่มาจากหน้าเว็บแก้ได้ด้วย DevTools
    ส่วนวิดีโอยังเชื่อค่าจากเบราว์เซอร์อยู่ เพราะ Render แผนฟรีไม่มี ffprobe ให้ใช้
    (แจ้งไว้ในแผนหัวข้อ 3.3)
    """
    try:
        from io import BytesIO

        from PIL import Image
    except ImportError:
        logger.warning("ยังไม่ได้ติดตั้ง Pillow จึงตรวจขนาดภาพฝั่ง backend ไม่ได้")
        return 0, 0

    try:
        with Image.open(BytesIO(content)) as image:
            return image.width, image.height
    except Exception as exc:
        logger.info("อ่านขนาดภาพไม่สำเร็จ: %s", exc)
        return 0, 0


def evaluate_media(items: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    ตรวจสื่อทุกไฟล์ของข่าวหนึ่งใบ คืนรายการพร้อมผลตรวจ

    รับค่าที่เบราว์เซอร์วัดมา (`width`/`height`) แล้ว **ตรวจซ้ำด้วย Pillow เมื่อเป็นภาพ
    และมีเนื้อไฟล์มาด้วย** ค่าจาก Pillow ชนะเสมอเพราะแก้จากฝั่งผู้ใช้ไม่ได้
    """
    results: List[Dict[str, Any]] = []

    for item in items or []:
        name = str(item.get("name") or "")
        mime = str(item.get("type") or "")
        width = item.get("width")
        height = item.get("height")
        source = "browser"

        if mime.startswith("image/"):
            content = item.get("_bytes")
            if content:
                w, h = inspect_image_bytes(content)
                if w and h:
                    width, height, source = w, h, "backend(Pillow)"

        passed, reason = check_dimensions(width, height)
        results.append(
            {
                "name": name,
                "type": mime,
                "width": int(width) if str(width or "").lstrip("-").isdigit() else 0,
                "height": int(height) if str(height or "").lstrip("-").isdigit() else 0,
                "size": item.get("size") or 0,
                "passed": passed,
                "reason": reason,
                "checkedBy": source,
                "url": str(item.get("url") or ""),
            }
        )

    return results


# ------------------------------------------------------------------ บันทึกข่าว


def prepare_news(
    form_data: Dict[str, Any],
    media: List[Dict[str, Any]],
    matched: List[str],
    folder_url: str = "ไม่มีไฟล์แนบ",
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """เตรียมแถวข่าวหนึ่งใบ (FR-01) — สถานะเริ่มต้นคือรออนุมัติเสมอ (FR-09)"""
    form = sanitize_form_data(form_data)
    record_id = record_id or generate_record_id("PR")

    source = str(form.get("source") or SOURCE_INTERNAL).strip().lower()
    if source not in KNOWN_SOURCES:
        raise PRError(f'แหล่งที่มา "{source}" ไม่อยู่ในรายการที่รองรับ')

    title = str(form.get("title") or "").strip()
    if not title:
        raise PRError("กรุณาระบุหัวข้อข่าว")

    needs_review = any(not m["passed"] for m in media)
    review_note = "; ".join(f"{m['name']}: {m['reason']}" for m in media if not m["passed"])

    now = datetime.now().isoformat()
    row_data = [
        record_id,
        now,
        now,
        form.get("actionBy", ""),
        STATUS_PENDING,
        True,
        str(form.get("newsDateTime", "")).split("T")[0] or now.split("T")[0],
        form.get("stationId", ""),
        form.get("unitId", ""),
        form.get("newsDateTime", ""),
        title,
        form.get("newsType", ""),
        source,
        form.get("content", ""),
        "",                                   # เนื้อหาที่เรียบเรียงแล้ว — รอ FR-06
        ", ".join(matched),
        form.get("reporterName", ""),
        "TRUE" if needs_review else "",
        review_note,
        folder_url,
        "",                                   # Post_ID — รอ FR-03
        "",                                   # Permalink — รอ FR-03
        "",                                   # วันเวลาที่เผยแพร่ — รอ FR-03
    ]

    return {
        "status": "success",
        "recordId": record_id,
        "targetDbId": get_target_db_id(form.get("stationId", "51")),
        "tableName": NEWS_TABLE,
        "rowData": row_data,
        "needsMediaReview": needs_review,
        "lineMessage": "",
        "lineGroupId": "",
    }


def prepare_media_rows(
    news_record_id: str,
    form_data: Dict[str, Any],
    media: List[Dict[str, Any]],
) -> List[List[Any]]:
    """แถวของไฟล์สื่อแต่ละไฟล์ ผูกกับข่าวด้วย News_RecordID"""
    form = sanitize_form_data(form_data)
    now = datetime.now().isoformat()
    actual_date = str(form.get("newsDateTime", "")).split("T")[0] or now.split("T")[0]

    rows: List[List[Any]] = []
    for index, item in enumerate(media, start=1):
        rows.append(
            [
                f"{news_record_id}-M{index:02d}",
                now,
                now,
                form.get("actionBy", ""),
                STATUS_PENDING if not item["passed"] else STATUS_APPROVED,
                True,
                actual_date,
                form.get("stationId", ""),
                form.get("unitId", ""),
                news_record_id,
                item["name"],
                item["type"],
                item["width"],
                item["height"],
                item["size"],
                "TRUE" if item["passed"] else "FALSE",
                item["reason"],
                item["checkedBy"],
                item["url"],
            ]
        )
    return rows


# --------------------------------------------------------- ตารางรวมข่าว (FR-04)


def _news_item(record: Dict[str, Any]) -> Dict[str, Any]:
    timestamp, raw_time = query_service._format_timestamp(record.get(query_service.COL_TIMESTAMP, ""))
    return {
        "recordId": record.get(query_service.COL_RECORD_ID, ""),
        "status": record.get(query_service.COL_STATUS, ""),
        "timestamp": timestamp,
        "rawTime": raw_time,
        "date": record.get(query_service.COL_ACTUAL_DATE, ""),
        "station": record.get(query_service.COL_STATION_ID, ""),
        "unit": record.get(query_service.COL_UNIT_ID, ""),
        "title": record.get("หัวข้อข่าว", ""),
        "newsType": record.get("ประเภทข่าว", ""),
        "source": record.get("แหล่งที่มา", ""),
        "content": record.get("เนื้อหาดิบ", ""),
        "matchedKeywords": [k for k in str(record.get("คำค้นที่ตรวจพบ", "")).split(",") if k.strip()],
        "reporter": record.get("ผู้ส่ง (ยศ ชื่อ สกุล)", ""),
        "needsMediaReview": str(record.get("ต้องตรวจคุณภาพสื่อ", "")).upper() == "TRUE",
        "reviewNote": record.get("หมายเหตุการตรวจ", ""),
        "attachments": record.get("Attachment_Folder", ""),
        "permalink": record.get("Permalink", ""),
    }


def list_news(
    station_id: str,
    start: str = "",
    end: str = "",
    source: str = "",
    news_type: str = "",
    keyword: str = "",
    status: str = "",
    only_needs_review: bool = False,
) -> List[Dict[str, Any]]:
    """
    ตารางรวมข่าวทุกแหล่ง พร้อมตัวกรอง (FR-04)

    **ไม่คืนแถวที่ถูกลบ (soft delete)** — FR-05 บอกให้เก็บถาวร ไม่ใช่ให้แสดงตลอดไป
    ถ้าต้องดูของที่ลบแล้วต้องเปิดชีตหรือทำหน้าแยก ซึ่งไม่ควรปนกับตารางใช้งานประจำวัน
    """
    spreadsheet_id = get_target_db_id(station_id)
    wanted_source = str(source or "").strip().lower()
    needle = str(keyword or "").strip().lower()

    items: List[Dict[str, Any]] = []
    for record in query_service.cached_rows(spreadsheet_id, NEWS_TABLE):
        if not query_service.is_active(record.get(query_service.COL_IS_ACTIVE)):
            continue
        if not query_service.check_station_match(station_id, record.get(query_service.COL_STATION_ID, "")):
            continue

        date_value = str(record.get(query_service.COL_ACTUAL_DATE, "") or "")[:10]
        if start and date_value and date_value < start:
            continue
        if end and date_value and date_value > end:
            continue
        if wanted_source and str(record.get("แหล่งที่มา", "")).lower() != wanted_source:
            continue
        if news_type and record.get("ประเภทข่าว", "") != news_type:
            continue
        if status and record.get(query_service.COL_STATUS, "") != status:
            continue
        if only_needs_review and str(record.get("ต้องตรวจคุณภาพสื่อ", "")).upper() != "TRUE":
            continue
        if needle:
            haystack = " ".join(
                str(record.get(column, ""))
                for column in ("หัวข้อข่าว", "เนื้อหาดิบ", "คำค้นที่ตรวจพบ", "ผู้ส่ง (ยศ ชื่อ สกุล)")
            ).lower()
            if needle not in haystack:
                continue

        items.append(_news_item(record))

    return sorted(items, key=lambda item: item["rawTime"], reverse=True)


def media_of(station_id: str, news_record_id: str) -> List[Dict[str, Any]]:
    """ไฟล์สื่อของข่าวหนึ่งใบ ใช้ในหน้าตรวจก่อนอนุมัติ"""
    spreadsheet_id = get_target_db_id(station_id)
    items: List[Dict[str, Any]] = []

    for record in query_service.cached_rows(spreadsheet_id, MEDIA_TABLE):
        if record.get("News_RecordID", "") != news_record_id:
            continue
        if not query_service.is_active(record.get(query_service.COL_IS_ACTIVE)):
            continue
        items.append(
            {
                "recordId": record.get(query_service.COL_RECORD_ID, ""),
                "name": record.get("ชื่อไฟล์", ""),
                "type": record.get("ชนิดไฟล์", ""),
                "width": query_service._to_int(record.get("ความกว้าง (px)")),
                "height": query_service._to_int(record.get("ความสูง (px)")),
                "passed": str(record.get("ผ่านเกณฑ์คุณภาพ", "")).upper() == "TRUE",
                "reason": record.get("เหตุผลที่ไม่ผ่าน", ""),
                "checkedBy": record.get("ที่มาของการตรวจ", ""),
                "url": record.get("File_Url", ""),
            }
        )
    return items


def summarize(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """ยอดสรุปที่หน้าตารางข่าวใช้แสดงบนหัวตาราง"""
    by_source: Dict[str, int] = {}
    for item in items:
        by_source[item["source"]] = by_source.get(item["source"], 0) + 1

    return {
        "total": len(items),
        "pending": sum(1 for i in items if i["status"] == STATUS_PENDING),
        "approved": sum(1 for i in items if i["status"] == STATUS_APPROVED),
        "needsMediaReview": sum(1 for i in items if i["needsMediaReview"]),
        "bySource": by_source,
    }


def export_rows(items: List[Dict[str, Any]]) -> List[List[Any]]:
    """แปลงเป็นตารางสำหรับส่งออก Excel (FR-04) หัวตารางอยู่แถวแรก"""
    header = [
        "รหัสข่าว", "สถานะ", "วันที่", "หัวข้อข่าว", "ประเภท", "แหล่งที่มา",
        "ผู้ส่ง", "หน่วย", "คำค้นที่ตรวจพบ", "ค้างตรวจสื่อ", "หมายเหตุการตรวจ",
    ]
    rows: List[List[Any]] = [header]
    for item in items:
        rows.append(
            [
                item["recordId"], item["status"], item["date"], item["title"],
                item["newsType"], item["source"], item["reporter"], item["unit"],
                ", ".join(item["matchedKeywords"]),
                "ใช่" if item["needsMediaReview"] else "",
                item["reviewNote"],
            ]
        )
    return rows
