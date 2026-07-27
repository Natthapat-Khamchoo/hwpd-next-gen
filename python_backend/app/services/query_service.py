"""
HWPD Next Gen - Read side.

report_service เตรียมแถวไปเขียน ส่วนโมดูลนี้อ่านกลับมา — คิวรออนุมัติ ประวัติของ
ตัวเอง รายการภารกิจ และการเปลี่ยนสถานะตอนอนุมัติ/ยกเลิก

ทุกตาราง (ยกเว้น tb_HQ_Summary) ขึ้นต้นด้วย 9 คอลัมน์มาตรฐานเหมือนกันหมด จึงอ่าน
ค่าที่ต้องใช้ได้จากชื่อคอลัมน์โดยไม่ต้องรู้ว่าเป็นรายงานประเภทไหน

เขียนกลับด้วย `RAW` เหมือนตอนบันทึกรายงาน เพื่อไม่ให้ Sheets ตีความค่าใหม่
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import check_station_match, get_target_db_id
from app.core.schema import get_columns
from app.services import sheets_service

logger = logging.getLogger(__name__)

# ชื่อคอลัมน์มาตรฐานที่โมดูลนี้ใช้ (ดู schema.SYSTEM_COLUMNS)
COL_RECORD_ID = "Sys_RecordID"
COL_TIMESTAMP = "Sys_Timestamp"
COL_LAST_UPDATE = "Sys_LastUpdate"
COL_ACTION_BY = "Sys_ActionBy"
COL_STATUS = "Sys_Status"
COL_IS_ACTIVE = "Sys_IsActive"
COL_ACTUAL_DATE = "Data_ActualDate"
COL_STATION_ID = "Data_StationID"
COL_UNIT_ID = "Data_UnitID"

STATUS_PENDING = "Pending"
STATUS_APPROVED = "Approved"
STATUS_CANCELED = "Canceled"

# ตารางที่เข้าคิวรออนุมัติ พร้อมป้ายและไอคอนที่หน้าเว็บใช้แสดง
# ตรงกับ sheetsToCheck ใน getPendingItemsGrouped / getMyPendingItems ของ รหัส.js
GENERAL_TABLES: List[Tuple[str, str, str]] = [
    ("tb_DailyResult", "ผลการปฏิบัติ/ว.20", "fa-chart-pie"),
    ("tb_Arrests", "รายงานจับกุม", "fa-handcuffs"),
    ("tb_Accidents", "รายงานอุบัติเหตุ", "fa-car-burst"),
    ("tb_RoyalGuard", "รายงานรับเสด็จ", "fa-shield-halved"),
    ("tb_OtherDuties", "ว.4 จิตอาสา/ช่วยเหลือ", "fa-hands-holding-child"),
]
FUEL_TABLES: List[Tuple[str, str, str]] = [
    ("tb_FuelOil", "น้ำมันรถยนต์", "fa-gas-pump"),
]

APPROVABLE_TABLES = {name for name, _, _ in GENERAL_TABLES + FUEL_TABLES}

VOLUNTEER_DUTY_TYPES = {"ทำจิตอาสา", "ว.4 ช่วยเหลือประชาชน"}


class RecordNotFound(LookupError):
    """ไม่พบรายการที่อ้างถึง อาจถูกลบไปแล้ว"""


def is_active(value: Any) -> bool:
    """ชีตเก็บ Sys_IsActive เป็น TRUE/FALSE บ้าง true/false บ้าง แล้วแต่ใครเขียน"""
    return str(value).strip().lower() == "true"


def _column_letter(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA (ตารางกว้างสุดตอนนี้ 34 คอลัมน์ จึงถึง AH)"""
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def read_rows(spreadsheet_id: str, table_name: str) -> List[Dict[str, Any]]:
    """
    อ่านทั้งตารางแล้วแปลงเป็น dict ตามชื่อคอลัมน์ใน schema พร้อมเลขแถวใน `_row`

    ใช้ชื่อคอลัมน์จาก schema ไม่ใช่หัวตารางในชีต เพราะชีตเดิมที่ Apps Script สร้างไว้
    มีป้ายที่ไม่ตรงกับข้อมูลอยู่บ้าง (ดูหมายเหตุใน schema.py) แต่ตำแหน่งตรงกันเสมอ
    """
    columns = get_columns(table_name)
    try:
        rows = sheets_service.read_table(spreadsheet_id, table_name)
    except sheets_service.SheetWriteError as exc:
        # ตารางที่ยังไม่เคยมีใครบันทึกลงไปจะยังไม่มีแท็บ ถือว่าไม่มีรายการ ไม่ใช่ error
        if "ไม่พบตาราง" in str(exc):
            logger.info("ยังไม่มีแท็บ %s ในสเปรดชีตนี้ ถือว่าไม่มีรายการ", table_name)
            return []
        raise

    records = []
    for line, row in enumerate(rows[1:], start=2):
        if not row or not str(row[0]).strip():
            continue
        record: Dict[str, Any] = {"_row": line}
        for index, column in enumerate(columns):
            record[column] = str(row[index]).strip() if index < len(row) else ""
        records.append(record)
    return records


def _format_timestamp(raw: str) -> Tuple[str, float]:
    """
    คืน (ข้อความแบบ dd/MM/yyyy HH:mm, เวลาแบบตัวเลขไว้เรียงลำดับ)

    ค่าที่เขียนไว้เป็น ISO จาก datetime.isoformat() แต่ข้อมูลเก่าที่ Apps Script
    เขียนไว้เป็นรูปแบบอื่น ถ้าแปลงไม่ได้ก็คืนค่าดิบไปแสดงตามเดิม
    """
    text = str(raw or "").strip()
    if not text:
        return "", 0.0
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return text, 0.0
    return parsed.strftime("%d/%m/%Y %H:%M"), parsed.timestamp()


def _pending_item(record: Dict[str, Any], table: str, label: str, icon: str) -> Dict[str, Any]:
    timestamp, raw_time = _format_timestamp(record.get(COL_TIMESTAMP, ""))
    return {
        "recordId": record.get(COL_RECORD_ID, ""),
        "timestamp": timestamp,
        "rawTime": raw_time,
        "formType": label,
        "sheetName": table,
        "icon": icon,
        "unit": record.get(COL_UNIT_ID, ""),
        "stationId": record.get(COL_STATION_ID, ""),
    }


def _is_pending(record: Dict[str, Any]) -> bool:
    return record.get(COL_STATUS, "") == STATUS_PENDING and is_active(record.get(COL_IS_ACTIVE))


def pending_for_station(
    station_id: str,
    tables: List[Tuple[str, str, str]],
    name_lookup: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    คิวรออนุมัติของสถานีนั้นและสถานีที่มองเห็นได้ เรียงจากเก่าไปใหม่ (คิวมาก่อนได้ก่อน)
    เทียบเท่า getPendingItemsGrouped ใน JS
    """
    spreadsheet_id = get_target_db_id(station_id)
    lookup = name_lookup or {}
    items: List[Dict[str, Any]] = []

    for table, label, icon in tables:
        for record in read_rows(spreadsheet_id, table):
            if not _is_pending(record):
                continue
            if not check_station_match(station_id, record.get(COL_STATION_ID, "")):
                continue

            item = _pending_item(record, table, label, icon)
            action_by = record.get(COL_ACTION_BY, "")
            item["reporter"] = lookup.get(action_by, action_by)
            item["details"] = _summarize(record, table)
            if table == "tb_FuelOil":
                item["plate"] = record.get("ทะเบียนรถ", "")
            if table == "tb_OtherDuties":
                item["isVolunteer"] = record.get("การปฏิบัติ", "") in VOLUNTEER_DUTY_TYPES
            items.append(item)

    return sorted(items, key=lambda item: item["rawTime"])


def pending_for_user(station_id: str, username: str) -> List[Dict[str, Any]]:
    """
    รายการของตัวเองที่ยังรออนุมัติ เรียงจากใหม่ไปเก่า (เพิ่งส่งอยู่บนสุด)
    เทียบเท่า getMyPendingItems ใน JS
    """
    spreadsheet_id = get_target_db_id(station_id)
    items: List[Dict[str, Any]] = []

    for table, label, icon in GENERAL_TABLES + FUEL_TABLES:
        for record in read_rows(spreadsheet_id, table):
            if _is_pending(record) and record.get(COL_ACTION_BY, "") == username:
                items.append(_pending_item(record, table, label, icon))

    return sorted(items, key=lambda item: item["rawTime"], reverse=True)


def _summarize(record: Dict[str, Any], table: str) -> str:
    """สรุปสั้น ๆ ให้แอดมินเห็นว่ารายการนี้คืออะไรโดยไม่ต้องกดเข้าไปดู"""
    if table == "tb_DailyResult":
        parts = [
            f"ว.43 = {record.get('ยอด ว.43', '0')}",
            f"บริการ = {record.get('ยอด บริการ', '0')}",
            f"ว.20 = {record.get('ยอด ว.20', '0')}",
        ]
        return ", ".join(parts)
    if table == "tb_FuelOil":
        litres = record.get("จำนวนลิตร", "")
        price = record.get("ราคาบาท", "")
        fuel_type = record.get("ประเภทน้ำมัน/รถ", "")
        return " ".join(part for part in (fuel_type, f"{litres} ลิตร" if litres else "", f"{price} บาท" if price else "") if part)
    if table == "tb_Arrests":
        return record.get("ข้อหาทั้งหมด", "") or record.get("หัวข้อการจับกุม", "")
    if table == "tb_Accidents":
        return record.get("ทล., กม., ตำบล, อำเภอ, จังหวัด", "")
    if table == "tb_RoyalGuard":
        return record.get("ชื่อภารกิจ", "")
    if table == "tb_OtherDuties":
        return record.get("การปฏิบัติ", "")
    return ""


def missions_for_unit(station_id: str, unit: str, start: str, end: str) -> List[Dict[str, Any]]:
    """
    ภารกิจในช่วงวันที่ที่ระบุ เว้น unit ว่างไว้ = ทุกหน่วยของสถานี
    เทียบวันที่ด้วยสตริง YYYY-MM-DD ได้ตรง ๆ เพราะ Data_ActualDate เก็บรูปแบบนั้น
    """
    spreadsheet_id = get_target_db_id(station_id)
    unit_filter = str(unit or "").strip()
    missions = []

    for record in read_rows(spreadsheet_id, "tb_Missions"):
        if not is_active(record.get(COL_IS_ACTIVE)):
            continue
        if not check_station_match(station_id, record.get(COL_STATION_ID, "")):
            continue

        actual_date = record.get(COL_ACTUAL_DATE, "")
        if start and actual_date < start:
            continue
        if end and actual_date > end:
            continue

        target_units = record.get("หน่วยบริการที่เกี่ยวข้อง - เก็บเป็นข้อความคั่นด้วยลูกน้ำ", "")
        if unit_filter and unit_filter not in target_units and unit_filter != record.get(COL_UNIT_ID, ""):
            continue

        missions.append(
            {
                "recordId": record.get(COL_RECORD_ID, ""),
                "startTime": record.get("วันที่เวลาเริ่มภารกิจ", ""),
                "endTime": record.get("วันที่เวลาสิ้นสุดภารกิจ", ""),
                "targetUnits": target_units,
                "details": record.get("รายละเอียดภารกิจ", ""),
                "location": record.get("สถานที่", ""),
                "actualDate": actual_date,
            }
        )

    return sorted(missions, key=lambda mission: (mission["actualDate"], mission["startTime"]))


def find_record(station_id: str, table_name: str, record_id: str) -> Dict[str, Any]:
    """หาแถวตาม recordId ขว้าง RecordNotFound ถ้าไม่เจอ"""
    spreadsheet_id = get_target_db_id(station_id)
    for record in read_rows(spreadsheet_id, table_name):
        if record.get(COL_RECORD_ID, "") == record_id:
            record["_spreadsheetId"] = spreadsheet_id
            return record
    raise RecordNotFound(f"ไม่พบรายการ {record_id} ใน {table_name} อาจถูกลบไปแล้ว")


def set_status(record: Dict[str, Any], table_name: str, status: str, active: bool) -> None:
    """
    เปลี่ยน Sys_Status / Sys_IsActive และประทับ Sys_LastUpdate

    Sys_ActionBy คั่นอยู่ระหว่าง LastUpdate กับ Status จึงส่งเป็นสองช่วงใน batch เดียว
    แทนการเขียนทับทั้งแถว ผู้ส่งรายงานคนเดิมจะได้ไม่ถูกทับด้วยค่าที่อ่านมาก่อนหน้า
    """
    columns = get_columns(table_name)
    line = record["_row"]
    last_update = _column_letter(columns.index(COL_LAST_UPDATE))
    status_col = _column_letter(columns.index(COL_STATUS))
    active_col = _column_letter(columns.index(COL_IS_ACTIVE))

    worksheet = sheets_service.get_worksheet(record["_spreadsheetId"], table_name, ensure=False)
    sheets_service.with_backoff(
        worksheet.batch_update,
        [
            {"range": f"{last_update}{line}", "values": [[datetime.now().isoformat()]]},
            {"range": f"{status_col}{line}:{active_col}{line}", "values": [[status, active]]},
        ],
        value_input_option="RAW",
    )
    logger.info("เปลี่ยนสถานะ %s ใน %s เป็น %s", record.get(COL_RECORD_ID, ""), table_name, status)


def _to_int(value: Any) -> int:
    try:
        return int(float(str(value).strip() or 0))
    except (TypeError, ValueError):
        return 0


def _accumulate_totals(record: Dict[str, Any], table: str, totals: Dict[str, int]) -> None:
    """
    ยอดสะสมนับเฉพาะแถวที่ผ่านการตรวจแล้วและยัง active

    ถ้านับ Pending ด้วย ตัวเลขบนการ์ด KPI จะขึ้นทันทีที่มีคนกดส่ง แล้วลดลงอีกครั้ง
    เมื่อแอดมินตีกลับ ซึ่งอ่านเหมือนระบบนับผิด
    """
    if record.get(COL_STATUS, "") == STATUS_PENDING or not is_active(record.get(COL_IS_ACTIVE)):
        return

    if table == "tb_DailyResult":
        totals["v43"] += _to_int(record.get("ยอด ว.43"))
        totals["v42"] += _to_int(record.get("ยอด ว.42"))
        totals["v20"] += _to_int(record.get("ยอด ว.20"))
    elif table == "tb_Arrests":
        totals["arrest"] += 1
    elif table == "tb_RoyalGuard":
        totals["royalGuard"] += 1
    elif table == "tb_OtherDuties" and record.get("การปฏิบัติ", "") in VOLUNTEER_DUTY_TYPES:
        totals["volunteer"] += 1


def station_overview(
    station_id: str,
    name_lookup: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    ทุกอย่างที่หน้า Admin ต้องใช้ในรอบเดียว — คิวรออนุมัติ คิวน้ำมัน และยอดสรุป

    เดิมแยกเป็นสามฟังก์ชันซึ่งอ่านตารางเดิมซ้ำกัน รวมแล้ว 16 ครั้งต่อการโหลดหนึ่งหน้า
    ชนเพดาน 60 ครั้ง/นาทีของ Google ตั้งแต่แอดมินคนที่สี่กดรีเฟรช ตอนนี้อ่านตารางละ
    ครั้งเดียวแล้วแยกผลในรอบเดียวกัน เหลือ 6 ครั้ง
    """
    spreadsheet_id = get_target_db_id(station_id)
    lookup = name_lookup or {}
    today = datetime.now().strftime("%Y-%m-%d")

    pending: List[Dict[str, Any]] = []
    fuel: List[Dict[str, Any]] = []
    totals = {"v43": 0, "v42": 0, "v20": 0, "arrest": 0, "volunteer": 0, "royalGuard": 0}
    approved = 0

    for table, label, icon in GENERAL_TABLES + FUEL_TABLES:
        for record in read_rows(spreadsheet_id, table):
            if not check_station_match(station_id, record.get(COL_STATION_ID, "")):
                continue

            if _is_pending(record):
                item = _pending_item(record, table, label, icon)
                action_by = record.get(COL_ACTION_BY, "")
                item["reporter"] = lookup.get(action_by, action_by)
                item["details"] = _summarize(record, table)
                if table == "tb_FuelOil":
                    item["plate"] = record.get("ทะเบียนรถ", "")
                    fuel.append(item)
                else:
                    if table == "tb_OtherDuties":
                        item["isVolunteer"] = record.get("การปฏิบัติ", "") in VOLUNTEER_DUTY_TYPES
                    pending.append(item)
                continue

            _accumulate_totals(record, table, totals)

            # Sys_LastUpdate คือเวลาที่กดอนุมัติ ไม่ใช่เวลาที่ส่งรายงาน
            if record.get(COL_STATUS, "") == STATUS_APPROVED and str(
                record.get(COL_LAST_UPDATE, "")
            ).startswith(today):
                approved += 1

    pending.sort(key=lambda item: item["rawTime"])
    fuel.sort(key=lambda item: item["rawTime"])

    return {
        "pending": pending,
        "fuel": fuel,
        "stats": {
            "pendingCount": len(pending),
            "fuelCount": len(fuel),
            "approvedToday": approved,
            **totals,
        },
    }
