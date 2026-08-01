"""
ค้นหาเชิงลึกข้ามตาราง — เทียบเท่า searchStationRecords / getCommanderDeepSearch /
getNationalDeepSearch ใน Apps Script เดิม

ใช้กับปุ่ม "แกะรอยผลงาน" ของผู้กำกับการ และ "ค้นหาทุกกอง" ของ ผบก. ทำงานเฉพาะตอน
กดค้นหา ไม่โหลดอัตโนมัติ เพราะระดับประเทศต้องเปิด 8 สเปรดชีต x 7 ตาราง

ของเดิมระบุคอลัมน์ที่ค้นเป็นเลขตำแหน่ง (textCols: [3, 10, 11, 15, 17, 18, 23]) ซึ่ง
เลื่อนทันทีที่มีใครแทรกคอลัมน์ ที่นี่อ่านเป็น dict ตามชื่อคอลัมน์อยู่แล้ว จึงค้นทุกช่อง
ที่เป็นข้อความยกเว้นคอลัมน์ระบบ ได้ผลครอบคลุมกว่าและไม่พังเมื่อตารางเปลี่ยน
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.config import get_db_router, get_target_db_id
from app.services import query_service

logger = logging.getLogger(__name__)

# ตาราง -> ป้ายที่แสดงบนหน้าจอ ชุดเดียวกับ searchTargets ของเดิม
SEARCH_TABLES = {
    "tb_Arrests": "จับกุมคดีอาญา",
    "tb_DailyResult": "ผลปฏิบัติ (ว.20)",
    "tb_OtherDuties": "ว.4 จิตอาสา/อื่นๆ",
    "tb_Checkpoints": "ตั้งด่าน",
    "tb_Accidents": "อุบัติเหตุ",
    "tb_RoyalGuard": "รับเสด็จ",
    "tb_Missions": "แจ้งภารกิจ",
}

# ไม่ต้องเอาคอลัมน์ระบบมาจับคู่คำค้น ไม่งั้นพิมพ์ "active" แล้วได้ทุกแถวในระบบ
SKIPPED_COLUMNS = {
    query_service.COL_STATUS,
    query_service.COL_IS_ACTIVE,
    query_service.COL_TIMESTAMP,
    query_service.COL_LAST_UPDATE,
    "_row",
}

# ของเดิมนับเฉพาะแถวที่ผ่านการตรวจแล้ว รายการที่ยังรออนุมัติไม่ควรโผล่ในผลงาน
COUNTED_STATUSES = {query_service.STATUS_APPROVED, "Active"}

MAX_RESULTS = 300


def _matches(record: Dict[str, Any], keyword: str) -> List[str]:
    """คืนข้อความช่องที่ตรงคำค้น ถ้าไม่ตรงเลยคืนลิสต์ว่าง"""
    hits = []
    for column, value in record.items():
        if column in SKIPPED_COLUMNS or not isinstance(value, str):
            continue
        if keyword in value.lower():
            hits.append(f"{column}: {value}")
    return hits


def search_division(station_id: str, keyword: str, start: str, end: str) -> List[Dict[str, Any]]:
    """ค้นทุกตารางในฐานข้อมูลของ กก. ที่สถานีนั้นสังกัด"""
    keyword = (keyword or "").strip().lower()
    if not keyword:
        return []

    spreadsheet_id = get_target_db_id(station_id)
    results: List[Dict[str, Any]] = []

    for table, label in SEARCH_TABLES.items():
        try:
            rows = query_service.read_rows(spreadsheet_id, table)
        except Exception as exc:  # ตารางหายหรืออ่านไม่ได้ ไม่ควรทำให้ทั้งการค้นหาล้ม
            logger.warning("ค้น %s ไม่ได้ ข้ามไป: %s", table, exc)
            continue

        for record in rows:
            if str(record.get(query_service.COL_STATUS, "")) not in COUNTED_STATUSES:
                continue
            if not query_service.is_active(record.get(query_service.COL_IS_ACTIVE)):
                continue

            date_value = str(record.get(query_service.COL_ACTUAL_DATE, "") or "")[:10]
            if start and date_value and date_value < start:
                continue
            if end and date_value and date_value > end:
                continue

            hits = _matches(record, keyword)
            if not hits:
                continue

            results.append(
                {
                    "recordId": record.get(query_service.COL_RECORD_ID, ""),
                    "type": label,
                    "table": table,
                    "date": date_value,
                    "station": record.get(query_service.COL_STATION_ID, ""),
                    "unit": record.get(query_service.COL_UNIT_ID, ""),
                    "actionBy": record.get(query_service.COL_ACTION_BY, ""),
                    "matches": hits[:4],
                }
            )

    results.sort(key=lambda r: str(r.get("date", "")), reverse=True)
    return results[:MAX_RESULTS]


def search_national(keyword: str, start: str, end: str, divisions: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    ค้นข้ามทุก กก. ที่ตั้งค่าฐานข้อมูลไว้แล้ว

    กก. ที่อ่านไม่ได้จะถูกข้ามพร้อมเขียน log ไม่ใช่ทำให้ทั้งคำค้นล้ม — ของเดิมก็ทำแบบนี้
    เพราะผู้บริหารต้องการผลจาก 7 กองที่เหลือมากกว่าได้ error เปล่า ๆ
    """
    keyword = (keyword or "").strip().lower()
    if not keyword:
        return []

    targets = divisions or sorted(d for d, entry in get_db_router().items() if d != "0" and entry.get("OPS"))
    results: List[Dict[str, Any]] = []

    for division in targets:
        try:
            found = search_division(f"{division}0", keyword, start, end)
        except Exception as exc:
            logger.warning("ค้น กก.%s ไม่ได้ ข้ามไป: %s", division, exc)
            continue
        for row in found:
            row["divName"] = f"กก.{division}"
        results.extend(found)

    results.sort(key=lambda r: str(r.get("date", "")), reverse=True)
    return results[:MAX_RESULTS]
