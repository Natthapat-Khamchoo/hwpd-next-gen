"""
รวมยอดตามป้ายหมวดรายงาน (reportTags) ของข้อหา

แบบฟอร์มใน `tb_ReportCatalog` ส่วนใหญ่ระบุ `dataTags` เช่น ECIG, GUN, DRUG, WEIGHT
แล้วคาดหวังยอดเฉพาะหมวดนั้น ตัวนี้คือชั้นที่แปลง "ข้อหาที่ติดป้ายอะไรไว้" ให้เป็นตัวเลข

ป้ายมาจากสองแหล่ง ไม่ใช่แหล่งเดียว:

  tb_Arrests      คดีอาญา — นับเป็น "ราย" (ใบรายงาน) กับ "คน" (ผู้ต้องหา)
  tb_DailyResult  คดีจราจร — นับเป็น "ใบสั่ง" จากยอดที่เจ้าหน้าที่กรอกต่อข้อหา

ข้อหาจราจรอย่าง WEIGHT/SMOKE จึงไม่มีวันโผล่ใน tb_Arrests และคดียาเสพติดก็ไม่โผล่ใน
tb_DailyResult การอ่านแหล่งเดียวจะได้ศูนย์ครึ่งหนึ่งของรายงานโดยไม่มีอะไรบอก

นับเฉพาะแถวที่ผ่านการตรวจแล้ว (Approved/Active) เหมือนที่ national_service ทำ
"""

import logging
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from app.core.config import MASTER_SHEET_ID, get_db_router, get_target_db_id
from app.services import query_service, sheets_service

logger = logging.getLogger(__name__)

CHARGES_TABLE = "tb_Charges"
COL_CHARGE_NAME = "ชื่อข้อหา"
COL_CHARGE_TAGS = "reportTags (ป้ายหมวดรายงาน)"
COL_ACTIVE = "isActive"

ARREST_CHARGES_COLUMN = "ข้อหาทั้งหมด"
ARREST_SUSPECTS_COLUMN = "จำนวนผู้ต้องหา"
DAILY_CHARGES_COLUMN = "Charges_Detail"

COUNTED_STATUSES = {query_service.STATUS_APPROVED, "Active"}

# "ชื่อข้อหา (12)" ในช่องข้อหาของผลการปฏิบัติประจำวัน
_AMOUNT = re.compile(r"\((\d+)\)\s*$")


def charge_tags() -> Dict[str, Set[str]]:
    """ชื่อข้อหา (ตัวพิมพ์เล็ก) -> ชุดป้าย ข้อหาที่ปิดใช้งานยังนับ เพราะรายงานเก่ายังอ้างถึง"""
    rows = sheets_service.read_table(MASTER_SHEET_ID, CHARGES_TABLE)
    if not rows:
        return {}
    header = [str(h).strip() for h in rows[0]]
    if COL_CHARGE_NAME not in header or COL_CHARGE_TAGS not in header:
        return {}
    name_at, tags_at = header.index(COL_CHARGE_NAME), header.index(COL_CHARGE_TAGS)

    mapping: Dict[str, Set[str]] = {}
    for row in rows[1:]:
        name = str(row[name_at]).strip() if name_at < len(row) else ""
        raw = str(row[tags_at]).strip() if tags_at < len(row) else ""
        if not name or not raw:
            continue
        tags = {t.strip().upper() for t in raw.split(",") if t.strip()}
        if tags:
            mapping[name.lower()] = tags
    return mapping


def _tags_in(text: str, mapping: Dict[str, Set[str]]) -> Set[str]:
    """
    หาป้ายจากข้อความรายการข้อหา

    เทียบด้วยการค้นชื่อข้อหาในข้อความ ไม่ใช่ split ด้วยตัวคั่น เพราะฝั่งจับกุมเก็บเป็น
    "1. ข้อหา ก" ส่วนฝั่งประจำวันเก็บเป็น "ข้อหา ก (12) | ข้อหา ข (3)" คนละรูปแบบกัน
    และชื่อข้อหาบางตัวมีวงเล็บอยู่ในตัวเอง
    """
    haystack = str(text or "").lower()
    if not haystack:
        return set()
    found: Set[str] = set()
    for name, tags in mapping.items():
        if name in haystack:
            found |= tags
    return found


def _blank() -> Dict[str, int]:
    return {"cases": 0, "suspects": 0, "citations": 0}


def aggregate_division_tags(division: str, start: str, end: str,
                            mapping: Optional[Dict[str, Set[str]]] = None) -> Dict[str, Dict[str, int]]:
    """ยอดรายป้ายของ กก. เดียว"""
    mapping = mapping if mapping is not None else charge_tags()
    if not mapping:
        return {}

    spreadsheet_id = get_target_db_id(f"{division}0")
    result: Dict[str, Dict[str, int]] = defaultdict(_blank)

    def in_range(record) -> bool:
        if str(record.get(query_service.COL_STATUS, "")) not in COUNTED_STATUSES:
            return False
        if not query_service.is_active(record.get(query_service.COL_IS_ACTIVE)):
            return False
        date_value = str(record.get(query_service.COL_ACTUAL_DATE, "") or "")[:10]
        if start and date_value and date_value < start:
            return False
        if end and date_value and date_value > end:
            return False
        return True

    try:
        for record in query_service.read_rows(spreadsheet_id, "tb_Arrests"):
            if not in_range(record):
                continue
            tags = _tags_in(record.get(ARREST_CHARGES_COLUMN, ""), mapping)
            suspects = query_service._to_int(record.get(ARREST_SUSPECTS_COLUMN)) or 1
            for tag in tags:
                result[tag]["cases"] += 1
                result[tag]["suspects"] += suspects
    except Exception as exc:
        logger.warning("อ่าน tb_Arrests ของ กก.%s ไม่ได้: %s", division, exc)

    try:
        for record in query_service.read_rows(spreadsheet_id, "tb_DailyResult"):
            if not in_range(record):
                continue
            text = str(record.get(DAILY_CHARGES_COLUMN, "") or "")
            if not text:
                continue
            for part in text.split("|"):
                part = part.strip()
                if not part:
                    continue
                found = _AMOUNT.search(part)
                amount = int(found.group(1)) if found else 0
                for tag in _tags_in(part, mapping):
                    result[tag]["citations"] += amount
    except Exception as exc:
        logger.warning("อ่าน tb_DailyResult ของ กก.%s ไม่ได้: %s", division, exc)

    return dict(result)


def aggregate_national_tags(start: str, end: str,
                            divisions: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    ยอดรายป้ายของทุก กก. พร้อมยอดรวม

    กก. ที่อ่านไม่ได้ถูกข้ามพร้อม log ไม่ทำให้ทั้งรายงานล้ม เหมือน search_service
    """
    mapping = charge_tags()
    targets = divisions or sorted(
        d for d, entry in get_db_router().items() if d != "0" and entry.get("OPS")
    )

    by_division: Dict[str, Dict[str, Dict[str, int]]] = {}
    total: Dict[str, Dict[str, int]] = defaultdict(_blank)

    for division in targets:
        try:
            stats = aggregate_division_tags(division, start, end, mapping)
        except Exception as exc:
            logger.warning("รวมยอดตามป้ายของ กก.%s ไม่ได้: %s", division, exc)
            continue
        by_division[division] = stats
        for tag, values in stats.items():
            for key, number in values.items():
                total[tag][key] += number

    return {"byDivision": by_division, "total": dict(total), "divisions": targets}
