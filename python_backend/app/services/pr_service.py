"""
HWPD Next Gen - โมดูลประชาสัมพันธ์ (requirement ข้อ 13)

FR-01 รับข่าว, FR-02 กรองคำค้นและตรวจคุณภาพสื่อ, FR-04 ตารางรวมข่าว,
FR-05 เก็บถาวรแบบ soft delete พร้อม audit, FR-07 ประกอบชิ้นงานตามเทมเพลต,
FR-08 ลิงก์สาธารณะ, FR-09 สิทธิ์อนุมัติ, FR-10 รายงานข่าวค้างอนุมัติแยกตามสังกัด

ที่ยังไม่ได้ทำ: FR-03 ตั้งเวลาเผยแพร่จริง (รอ Facebook App Review) กับ FR-06
AI เกลาข้อความ (รอ API key) คอลัมน์ `Post_ID` / `Permalink` / `วันเวลาที่เผยแพร่`
เว้นไว้รอ FR-03 ส่วน `เนื้อหาที่เรียบเรียงแล้ว` รอ FR-06 — `compose()` หยิบไปใช้
เองอยู่แล้วเมื่อช่องนั้นมีค่า จึงไม่ต้องกลับมาแก้เทมเพลตอีกรอบ

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
from app.services.report_service import format_thai_date, generate_record_id

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
        "",                                   # เทมเพลตชิ้นงาน PR — เติมตอนสร้างลิงก์ (FR-07)
        "",                                   # Share_File_ID — เติมตอนสร้างลิงก์ (FR-08)
        "",                                   # Share_Url — เติมตอนสร้างลิงก์ (FR-08)
        "",                                   # วันเวลาที่สร้างลิงก์ — เติมตอนสร้างลิงก์ (FR-08)
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
        "polishedContent": record.get("เนื้อหาที่เรียบเรียงแล้ว", ""),
        "shareTemplate": record.get("เทมเพลตชิ้นงาน PR", ""),
        "shareFileId": record.get("Share_File_ID", ""),
        "shareUrl": record.get("Share_Url", ""),
        "sharedAt": record.get("วันเวลาที่สร้างลิงก์", ""),
    }


def news_item(record: Dict[str, Any]) -> Dict[str, Any]:
    """แถวข่าวดิบจากชีต → รูปที่หน้าเว็บกับ `compose()` ใช้ร่วมกัน"""
    return _news_item(record)


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


# ------------------------------------------- ประกอบชิ้นงาน PR ตามเทมเพลต (FR-07)


# เทมเพลตชิ้นงาน PR — ปลายทางคนละที่ กติกาการเขียนจึงคนละแบบ
#
# ทั้งสามอันประกอบจากข่าวใบเดียวกัน ต่างกันที่ความยาวและน้ำเสียง ไม่ได้ต่างที่ข้อมูล
# แยกเป็นสามแบบเพราะการเอาข้อความแถลงข่าวไปโพสต์เพจตรง ๆ ยาวเกินกว่าที่คนจะอ่านจบ
# ส่วนการเอาข้อความสั้นแบบเพจไปใช้เป็นเอกสารแถลงข่าวก็ขาดข้อมูลที่สื่อมวลชนต้องใช้
PR_TEMPLATES: Dict[str, str] = {
    "press": "ข่าวแจกสื่อมวลชน",
    "facebook": "โพสต์เพจ",
    "line": "ข้อความแจ้งกลุ่มไลน์",
}
DEFAULT_TEMPLATE = "press"

# ท้ายชิ้นงานทุกแบบ — ให้คนที่รับข่าวไปรู้ว่าถามกลับได้ที่ไหน
CONTACT_LINE = "กองบังคับการตำรวจทางหลวง (บก.ทล.) โทร. 1193 ตลอด 24 ชั่วโมง"


def _hashtags(item: Dict[str, Any]) -> str:
    """คำค้นที่ระบบจับได้ + แท็บประจำหน่วย แปลงเป็นแฮชแท็กสำหรับโพสต์เพจ"""
    words = ["ตำรวจทางหลวง", "1193"]
    words += [str(k).strip().replace(" ", "") for k in item.get("matchedKeywords", []) if str(k).strip()]

    seen: List[str] = []
    for word in words:
        if word and word not in seen:
            seen.append(word)
    return " ".join(f"#{word}" for word in seen)


def compose(item: Dict[str, Any], template: str = DEFAULT_TEMPLATE) -> str:
    """
    ประกอบข่าวหนึ่งใบเป็นชิ้นงาน PR ตามเทมเพลต (FR-07)

    ใช้ `เนื้อหาที่เรียบเรียงแล้ว` ก่อนถ้ามี ไม่งั้นใช้เนื้อหาดิบ — ช่องแรกเป็นของ FR-06
    ที่ยังไม่ได้ทำ แต่พอทำเมื่อไหร่ชิ้นงานจะหยิบไปใช้เองโดยไม่ต้องแก้ตรงนี้อีก

    คืนข้อความล้วน ไม่ใช่ HTML เพราะปลายทางคือช่องแปะข้อความของเพจ ของไลน์
    และของอีเมลถึงสื่อ ทั้งสามที่รับ markup ไม่เหมือนกันสักที่
    """
    key = str(template or DEFAULT_TEMPLATE).strip().lower()
    if key not in PR_TEMPLATES:
        raise PRError(f'ไม่รู้จักเทมเพลต "{template}" มีให้เลือก: {", ".join(PR_TEMPLATES)}')

    title = str(item.get("title") or "").strip()
    body = str(item.get("polishedContent") or item.get("content") or "").strip() or "(ไม่มีเนื้อหา)"
    date_text = format_thai_date(str(item.get("date") or "")) or "-"
    unit = str(item.get("unit") or "").strip()
    reporter = str(item.get("reporter") or "").strip()
    news_type = str(item.get("newsType") or "").strip()

    if key == "facebook":
        parts = [title, "", body, "", _hashtags(item)]
        return "\n".join(parts).strip() + "\n"

    if key == "line":
        parts = [
            f"[ประชาสัมพันธ์ {news_type}]".replace(" ]", "]"),
            title,
            f"วันที่ {date_text}" + (f" · {unit}" if unit else ""),
            "",
            body,
            "",
            CONTACT_LINE,
        ]
        return "\n".join(parts).strip() + "\n"

    # press — ข่าวแจกสื่อมวลชน ข้อมูลครบที่สุดในสามแบบ
    header = "ข่าวประชาสัมพันธ์ กองบังคับการตำรวจทางหลวง"
    parts = [
        header,
        "=" * len(header),
        "",
        f"เรื่อง  {title}",
        f"วันที่  {date_text}",
    ]
    if unit:
        parts.append(f"หน่วย   {unit}")
    if news_type:
        parts.append(f"ประเภท  {news_type}")
    parts += ["", body, ""]
    if reporter:
        parts.append(f"ผู้ให้ข่าว  {reporter}")
    parts.append(CONTACT_LINE)
    return "\n".join(parts).strip() + "\n"


def artifact_filename(record_id: str, template: str) -> str:
    """ชื่อไฟล์ชิ้นงาน PR บน Drive — ขึ้นต้นด้วยรหัสข่าวเพื่อให้เรียงตามข่าวในโฟลเดอร์"""
    return f"{record_id}_PR_{str(template or DEFAULT_TEMPLATE).strip().lower()}.txt"


# --------------------------------- รายงานข่าวค้างอนุมัติแยกตามสังกัด (FR-10)


# ช่วงอายุของข่าวที่ยังค้างคิว — เป็นวัน นับจากวันที่ส่ง
#
# แบ่งช่วงเพราะยอดรวมอย่างเดียวไม่บอกว่าปัญหาอยู่ตรงไหน ข่าวค้าง 20 ใบที่เพิ่งส่ง
# วันนี้คือคิวปกติ แต่ค้าง 3 ใบมาเจ็ดวันแปลว่ามีคนลืม สองกรณีนี้ต้องแยกกันให้เห็น
AGING_BUCKETS = (
    ("today", "ภายในวันนี้", 0, 0),
    ("d1_3", "1-3 วัน", 1, 3),
    ("d4_7", "4-7 วัน", 4, 7),
    ("over7", "เกิน 7 วัน", 8, 10**6),
)


def _age_in_days(date_value: str, today: Optional[str] = None) -> int:
    """จำนวนวันที่ข่าวค้างอยู่ คืน 0 เมื่ออ่านวันที่ไม่ได้ เพื่อไม่ให้ข้อมูลเสียดันยอดค้างนาน"""
    reference = today or datetime.now().date().isoformat()
    try:
        start = datetime.fromisoformat(str(date_value or "")[:10]).date()
        end = datetime.fromisoformat(reference[:10]).date()
    except ValueError:
        return 0
    return max((end - start).days, 0)


def _bucket_of(days: int) -> str:
    for key, _label, low, high in AGING_BUCKETS:
        if low <= days <= high:
            return key
    return AGING_BUCKETS[-1][0]


def pending_report(
    station_id: str,
    start: str = "",
    end: str = "",
    today: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ข่าวที่ยังรออนุมัติ จัดกลุ่มตามสังกัด (FR-10)

    "สังกัด" ใช้ `Data_UnitID` ก่อน เพราะเป็นหน่วยที่เจ้าหน้าที่สังกัดจริง ข่าวที่ไม่มี
    หน่วยกำกับไว้ตกไปอยู่กลุ่มของสถานี ไม่ถูกทิ้ง — ข่าวที่หายจากรายงานค้างอนุมัติ
    คือข่าวที่ไม่มีใครอนุมัติให้ตลอดกาล

    เรียงกลุ่มตามใบที่ค้างนานที่สุดก่อน ไม่ใช่ตามจำนวน คนอ่านรายงานนี้เพื่อหาว่าต้อง
    ไปตามใคร ไม่ใช่เพื่อดูว่าหน่วยไหนส่งข่าวเยอะ
    """
    items = list_news(station_id, start=start, end=end, status=STATUS_PENDING)

    groups: Dict[str, Dict[str, Any]] = {}
    buckets = {key: 0 for key, _label, _low, _high in AGING_BUCKETS}

    for item in items:
        days = _age_in_days(item.get("date", ""), today)
        bucket = _bucket_of(days)
        buckets[bucket] += 1

        name = str(item.get("unit") or "").strip() or f'สถานี {item.get("station") or "ไม่ระบุ"}'
        group = groups.setdefault(
            name,
            {
                "unit": name,
                "station": item.get("station", ""),
                "total": 0,
                "needsMediaReview": 0,
                "oldestDays": 0,
                "items": [],
            },
        )
        group["total"] += 1
        group["needsMediaReview"] += 1 if item.get("needsMediaReview") else 0
        group["oldestDays"] = max(group["oldestDays"], days)
        group["items"].append({**item, "waitingDays": days, "bucket": bucket})

    for group in groups.values():
        group["items"].sort(key=lambda i: i["waitingDays"], reverse=True)

    ordered = sorted(groups.values(), key=lambda g: (-g["oldestDays"], -g["total"], g["unit"]))

    return {
        "groups": ordered,
        "totals": {
            "pending": len(items),
            "units": len(ordered),
            "needsMediaReview": sum(g["needsMediaReview"] for g in ordered),
            "oldestDays": max((g["oldestDays"] for g in ordered), default=0),
        },
        "aging": [
            {"key": key, "label": label, "count": buckets[key]}
            for key, label, _low, _high in AGING_BUCKETS
        ],
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
