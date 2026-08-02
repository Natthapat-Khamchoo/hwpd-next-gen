"""
HWPD Next Gen - หน้า ฝอ.กก. และหน้าผู้กำกับการ

พอร์ตมาจาก รหัส.js ส่วน "ระบบ HQ Dashboard" — น้ำมัน กำลังพล ของกลาง นำขบวน
รายละเอียดรายวัน และข้อมูลชุดที่หน้าผู้กำกับการใช้ (ภาพรวมผู้บริหาร ปฏิทินภารกิจ
สั่งการผ่าน LINE)

ของเดิมอ้างคอลัมน์ด้วยตัวเลข (row[14], row[16]) ที่นี่อ้างด้วยชื่อจาก schema
ตำแหน่งเท่ากันแต่อ่านออกว่ากำลังหยิบอะไร

ทุกฟังก์ชันอ่านผ่าน query_service.cached_rows ยกเว้นเส้นทางที่ต้องเขียนกลับ
ซึ่งต้องใช้ read_rows เพื่อให้ได้ `_row` ที่ยังตรงกับชีตจริง
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import (
    MASTER_SHEET_ID,
    get_division_stations,
    get_station_config,
    get_station_data,
    get_target_db_id,
)
from app.services import query_service, sheets_service

logger = logging.getLogger(__name__)

FUEL_QUOTA_TABLE = "tb_FuelQuota"
ESCORT_TABLE = "tb_HQ_Escorts"
USERS_TABLE = "tb_Users"

# ประเภทรายการใน tb_FuelOil ที่นับเป็นน้ำมันเครื่อง ของเดิมยอมรับสองคำเพราะฟอร์ม
# รุ่นเก่ากับรุ่นใหม่เขียนไม่เหมือนกัน
OIL_CHANGE_TYPES = {"เปลี่ยนน้ำมันเครื่อง", "เปลี่ยนถ่ายน้ำมันเครื่อง"}
REFUEL_TYPE = "เติมน้ำมัน"


def _to_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def _station_name(station_id: str) -> str:
    """"ฝอ.กก.5" สำหรับรหัสลงท้าย 0 ไม่งั้น "ส.ทล.1 (สระบุรี)" ตามที่ของเดิมประกอบไว้"""
    division, number = station_id[:1], station_id[1:]
    if number == "0":
        return f"ฝอ.กก.{division}"
    province = get_station_data(station_id).get("province", "")
    return f"ส.ทล.{number} ({province})" if province else f"ส.ทล.{number}"


def _user_names() -> Dict[str, str]:
    """username -> ชื่อเต็ม ใช้แปลงชื่อผู้ใช้ในรายงานให้เป็นชื่อคนที่อ่านรู้เรื่อง"""
    names: Dict[str, str] = {}
    for record in query_service.cached_rows(MASTER_SHEET_ID, USERS_TABLE):
        username = str(record.get("Username", "")).strip()
        if username:
            names[username] = str(record.get("FullName", "")).strip()
    return names


def _date_part(value: str) -> str:
    """
    ดึงเฉพาะ yyyy-MM-dd ออกจากค่าที่ชีตอาจเก็บไว้หลายแบบ

    ค่าที่เจอจริง: "2026-07-31", "2026-07-31T08:30:00", "31/07/2026 08:30"
    ของเดิมโยนเข้า new Date() ซึ่งเดาให้เอง ที่นี่ต้องแยกเองเพราะ Python ไม่เดา
    """
    text = str(value or "").strip()
    if not text:
        return ""
    iso = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso:
        return iso.group(0)
    thai = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if thai:
        day, month, year = thai.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return ""


def _in_range(value: str, start: str, end: str) -> bool:
    day = _date_part(value)
    if not day:
        return False
    return (not start or day >= start) and (not end or day <= end)


def _sort_key(value: str) -> str:
    """เรียงตามวันเวลาแบบ ISO ค่าที่แปลงไม่ได้ไปอยู่ท้ายสุด"""
    text = str(value or "").strip()
    return text if re.match(r"\d{4}-\d{2}-\d{2}", text) else _date_part(text) or "0000"


def _display_datetime(value: str) -> str:
    """
    แปลงเป็น dd/MM/yyyy HH:mm ให้ตรงกับที่ของเดิมส่งไปหน้าเว็บ

    Sys_Timestamp ที่ฝั่ง Python เขียนมีเศษวินาทีติดมาด้วย (2026-07-31T17:30:41.626967)
    ซึ่ง strptime แบบระบุรูปแบบตายตัวแปลงไม่ได้ แล้วหน้าเว็บจะโชว์สตริงดิบทั้งก้อน
    fromisoformat รับได้ทั้งมีและไม่มีเศษวินาที จึงใช้เป็นตัวแรก
    """
    text = str(value or "").strip()
    if not text:
        return "-"
    try:
        return datetime.fromisoformat(text.replace(" ", "T")).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        pass
    for pattern in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            continue
    return text


def _time_part(value: str) -> str:
    match = re.search(r"(\d{2}):(\d{2})", str(value or ""))
    return match.group(0) if match else "-"


def _station_key(raw: str) -> str:
    """
    รหัสสถานีในรายงานบางแถวยาวเกินสองหลัก ของเดิมตัดหลักแรกทิ้ง

    ตรงนี้ทำแบบเดียวกันเพื่อให้ยอดตกถังเดียวกับที่หน้าเดิมเคยแสดง
    """
    text = str(raw or "").strip()
    return text[1:] if len(text) > 2 else text


# ---------------------------------------------------------------- น้ำมัน


def fuel_summary(station_id: str, month_year: str) -> Dict[str, Any]:
    """
    ยอดโควตาและยอดใช้จริงรายสถานีของเดือนที่เลือก พร้อมรายการเบิกทีละใบ

    month_year เป็น yyyy-MM ตรงกับที่ tb_FuelQuota เก็บ
    """
    spreadsheet_id = get_target_db_id(station_id)
    stations = get_division_stations(station_id, include_hq=True)
    division = stations[0][:1] if stations else station_id[:1]

    blank = {"quotaL": 0.0, "quotaB": 0.0, "usedL": 0.0, "usedB": 0.0, "oilQuotaL": 0.0, "oilUsedL": 0.0}
    summary: Dict[str, Dict[str, Any]] = {"total": {"name": f"รวม กก.{division}", **blank}}
    for sid in stations:
        summary[sid] = {"name": _station_name(sid), **blank}

    for record in query_service.cached_rows(spreadsheet_id, FUEL_QUOTA_TABLE):
        if str(record.get("MonthYear", "")).strip().lstrip("'")[:7] != month_year:
            continue
        key = _station_key(record.get("StationID", ""))
        if key in summary:
            summary[key]["quotaB"] = _to_float(record.get("QuotaBaht"))
            summary[key]["oilQuotaL"] = _to_float(record.get("QuotaOilLiters"))

    for key, bucket in summary.items():
        if key != "total":
            summary["total"]["quotaB"] += bucket["quotaB"]
            summary["total"]["oilQuotaL"] += bucket["oilQuotaL"]

    names = _user_names()
    logs: List[Dict[str, Any]] = []

    for record in query_service.cached_rows(spreadsheet_id, "tb_FuelOil"):
        if record.get(query_service.COL_STATUS) not in ("Pending", "Approved"):
            continue
        when = record.get("วันเวลาที่ทำรายการ") or record.get(query_service.COL_ACTUAL_DATE)
        if _date_part(when)[:7] != month_year:
            continue

        key = _station_key(record.get(query_service.COL_STATION_ID, ""))
        kind = str(record.get("ประเภทรายการ", "")).strip()
        liters = _to_float(record.get("จำนวนลิตร"))
        baht = _to_float(record.get("ราคาบาท"))

        if key in summary:
            if kind == REFUEL_TYPE:
                summary[key]["usedL"] += liters
                summary[key]["usedB"] += baht
                summary["total"]["usedL"] += liters
                summary["total"]["usedB"] += baht
            elif kind in OIL_CHANGE_TYPES:
                summary[key]["oilUsedL"] += liters
                summary["total"]["oilUsedL"] += liters

        operator = str(record.get("ผู้ดำเนินการ", "")).strip()
        action_by = str(record.get(query_service.COL_ACTION_BY, "")).strip()
        logs.append(
            {
                "date": _display_datetime(record.get(query_service.COL_TIMESTAMP)),
                "sortKey": _sort_key(record.get(query_service.COL_TIMESTAMP)),
                "station": summary[key]["name"] if key in summary else f"ส.ทล.{key}",
                "unit": record.get(query_service.COL_UNIT_ID, ""),
                "type": kind,
                # ช่อง "ผู้ดำเนินการ" กรอกได้ทั้งชื่อผู้ใช้และชื่อคนแบบพิมพ์เอง ถ้าเป็นชื่อผู้ใช้
                # ก็แปลงเป็นชื่อเต็ม ถ้าเป็นชื่อที่พิมพ์มาก็แสดงตามนั้น — ห้ามตกไปใช้ชื่อบัญชี
                # ที่กดส่ง เพราะบัญชีเป็นของสถานี คนอ่านจะเห็น "ส.ทล.1 กก.5" แทนชื่อคนจริง
                "person": names.get(operator) or operator or names.get(action_by) or action_by,
                "car": record.get("ทะเบียนรถ", ""),
                "currentMileage": record.get("เลขไมล์ปัจจุบัน") or "-",
                "liters": liters,
                "fuelType": record.get("ประเภทน้ำมัน/รถ") or "-",
                "baht": baht,
                "receipt": record.get("เลขที่ใบเสร็จ") or "-",
                "prevMileage": record.get("เลขไมล์ครั้งก่อน") or "-",
                "distance": record.get("ระยะทางใช้งาน(กม.)") or "-",
            }
        )

    logs.sort(key=lambda item: item["sortKey"])
    return {"summary": summary, "logs": logs}


def save_fuel_quota(station_id: str, month_year: str, quotas: List[Dict[str, Any]], action_by: str) -> int:
    """
    ตั้งโควตาของเดือน — มีแถวเดิมก็ทับ ไม่มีก็ต่อท้าย คืนจำนวนสถานีที่บันทึก

    เขียนทีเดียวหลายเซลล์ผ่าน batch_update ไม่ใช่ยิงทีละช่องแบบของเดิม เพราะ
    หนึ่ง กก. มีได้ถึง 7 สถานี = 35 คำขอ ซึ่งกินโควตา Sheets เกินจำเป็น
    """
    spreadsheet_id = get_target_db_id(station_id)
    worksheet = sheets_service.get_worksheet(spreadsheet_id, FUEL_QUOTA_TABLE)
    existing = query_service.read_rows(spreadsheet_id, FUEL_QUOTA_TABLE)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    by_station = {
        str(record.get("StationID", "")).strip(): record["_row"]
        for record in existing
        if str(record.get("MonthYear", "")).strip().lstrip("'")[:7] == month_year
    }

    updates: List[Dict[str, Any]] = []
    appends: List[List[Any]] = []
    for quota in quotas:
        target = str(quota.get("stationId", "")).strip()
        if not target:
            continue
        values = [0, _to_float(quota.get("baht")), stamp, action_by, _to_float(quota.get("oilLiters"))]
        row = by_station.get(target)
        if row:
            updates.append({"range": f"C{row}:G{row}", "values": [values]})
        else:
            appends.append([f"'{month_year}", target] + values)

    if updates:
        sheets_service.with_backoff(worksheet.batch_update, updates, value_input_option="RAW")
    for row in appends:
        sheets_service.append_report_row(spreadsheet_id, FUEL_QUOTA_TABLE, row)

    query_service.invalidate_cache(spreadsheet_id, FUEL_QUOTA_TABLE)
    return len(updates) + len(appends)


# ------------------------------------------------------------- กำลังพล


def _help_active(help_station: str, start: str, end: str) -> bool:
    """
    การช่วยราชการยังมีผลอยู่ไหม ณ วันนี้

    ไม่ระบุวันที่ = ยังมีผลตลอด ตามที่ isHelpAssignmentActive ของเดิมตั้งใจไว้
    ระบุมาข้างเดียวก็ยอมรับ เพราะข้อมูลเก่าหลายแถวกรอกแค่วันเริ่ม
    """
    if not str(help_station or "").strip():
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    start_day, end_day = _date_part(start), _date_part(end)
    if start_day and today < start_day:
        return False
    if end_day and today > end_day:
        return False
    return True


def _rank_group(full_name: str) -> str:
    """
    แบ่งชั้นยศไว้วางผังกำลังพลสามแถว ตามเงื่อนไขเดิมใน getManpowerData

    ลำดับการเช็คสำคัญ — "รอง สว." มีคำว่า "สว." อยู่ในตัว ถ้าเช็คสลับกันจะถูกจัด
    ขึ้นแถวบนหมด
    """
    if "รอง สว." in full_name:
        return "level2"
    if "ผกก." in full_name or "สวญ." in full_name or "สว." in full_name:
        return "level1"
    return "level3"


def manpower_data(station_id: str) -> Dict[str, Any]:
    """ผังกำลังพลของสถานีเดียว แยกตามชั้นยศ พร้อมคนที่มาช่วยราชการจากที่อื่น"""
    target = str(station_id).strip()
    stats = {"base": 0, "out": 0, "in": 0, "net": 0}
    chart: Dict[str, List[Dict[str, Any]]] = {"level1": [], "level2": [], "level3": [], "incoming": []}

    for record in query_service.cached_rows(MASTER_SHEET_ID, USERS_TABLE):
        full_name = str(record.get("FullName", "")).strip()
        if not full_name:
            continue

        home = str(record.get("Station_ID", "")).strip()
        help_station = str(record.get("สถานะไปช่วยราชการ", "")).strip()
        helping = _help_active(help_station, record.get("วันที่เริ่มช่วยราชการ"), record.get("วันที่สิ้นสุดช่วยราชการ"))
        common = {
            "username": str(record.get("Username", "")).strip(),
            "name": full_name,
            "remark": str(record.get("หมายเหตุ", "")).strip(),
            "phone": str(record.get("เบอร์โทร", "")).strip(),
            "code": str(record.get("รหัส", "")).strip(),
        }

        if helping and help_station == target and home != target:
            chart["incoming"].append(
                {**common, "homeStation": home, "homeStationLabel": get_station_data(home).get("fullName", home)}
            )
            continue

        if home != target:
            continue

        leaving = helping and help_station != target
        stats["base"] += 1
        if leaving:
            stats["out"] += 1

        chart[_rank_group(full_name)].append(
            {
                **common,
                "status": "out" if leaving else "normal",
                "tag": get_station_data(help_station).get("fullName", "") if leaving else "",
                "rawOutStation": help_station,
                "rawStart": _date_part(record.get("วันที่เริ่มช่วยราชการ")),
                "rawEnd": _date_part(record.get("วันที่สิ้นสุดช่วยราชการ")),
            }
        )

    stats["in"] = len(chart["incoming"])
    stats["net"] = stats["base"] - stats["out"] + stats["in"]
    return {"stats": stats, "chart": chart}


def manpower_overview(station_id: str) -> Dict[str, Dict[str, Any]]:
    """ยอดกำลังพลทุกสถานีใน กก. — ฐาน ไปช่วย มาช่วย และยอดที่เหลือปฏิบัติจริง"""
    stations = get_division_stations(station_id, include_hq=True)
    summary: Dict[str, Dict[str, Any]] = {"total": {"name": "รวมทั้ง กก.", "base": 0, "out": 0, "in": 0, "net": 0}}
    for sid in stations:
        summary[sid] = {"name": _station_name(sid), "base": 0, "out": 0, "in": 0, "net": 0}

    for record in query_service.cached_rows(MASTER_SHEET_ID, USERS_TABLE):
        if not str(record.get("FullName", "")).strip():
            continue

        home = str(record.get("Station_ID", "")).strip()
        help_station = str(record.get("สถานะไปช่วยราชการ", "")).strip()
        home_key = home[-2:] if len(home) > 2 else home
        help_key = help_station[-2:] if len(help_station) > 2 else help_station
        helping = _help_active(help_station, record.get("วันที่เริ่มช่วยราชการ"), record.get("วันที่สิ้นสุดช่วยราชการ"))

        if home_key in summary:
            summary[home_key]["base"] += 1
            summary["total"]["base"] += 1
            if helping and help_key != home_key:
                summary[home_key]["out"] += 1
                summary["total"]["out"] += 1

        # นับจากปลายทาง ไม่ว่าต้นสังกัดจะอยู่ กก. ไหน จุดเดียวที่ข้อมูลข้าม กก. มาบรรจบกัน
        if helping and help_key != home_key and help_key in summary:
            summary[help_key]["in"] += 1
            summary["total"]["in"] += 1

    for bucket in summary.values():
        bucket["net"] = bucket["base"] - bucket["out"] + bucket["in"]
    return summary


def update_manpower_status(
    username: str, help_station: str, start: str, end: str, remark: str
) -> str:
    """ตั้ง/ยกเลิกสถานะช่วยราชการของเจ้าหน้าที่หนึ่งคน คืนชื่อที่แก้"""
    target = str(help_station or "").strip()
    if target and target not in get_station_config():
        raise ValueError(f'รหัสสถานีไม่ถูกต้อง: "{target}"')

    worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, USERS_TABLE)
    for record in query_service.read_rows(MASTER_SHEET_ID, USERS_TABLE):
        if str(record.get("Username", "")).strip() != str(username).strip():
            continue
        row = record["_row"]
        sheets_service.with_backoff(
            worksheet.batch_update,
            [
                {"range": f"G{row}", "values": [[target]]},
                {"range": f"I{row}", "values": [[remark or ""]]},
                {"range": f"L{row}:M{row}", "values": [[start or "", end or ""]]},
            ],
            value_input_option="RAW",
        )
        query_service.invalidate_cache(MASTER_SHEET_ID, USERS_TABLE)
        return str(record.get("FullName", "")).strip() or username

    raise LookupError("ไม่พบข้อมูลเจ้าหน้าที่ในระบบ")


# ------------------------------------------------------------- ของกลาง


def evidence_list(station_id: str, start: str, end: str) -> List[Dict[str, Any]]:
    """คดีจับกุมที่อนุมัติแล้ว พร้อมสถานะว่าจัดหมวดหมู่ของกลางแล้วหรือยัง"""
    spreadsheet_id = get_target_db_id(station_id)
    results: List[Dict[str, Any]] = []

    for record in query_service.cached_rows(spreadsheet_id, "tb_Arrests"):
        if record.get(query_service.COL_STATUS) != query_service.STATUS_APPROVED:
            continue
        if not query_service.is_active(record.get(query_service.COL_IS_ACTIVE)):
            continue
        when = record.get("วันที่เวลาที่รายงาน") or record.get(query_service.COL_TIMESTAMP)
        if (start or end) and not _in_range(when, start, end):
            continue

        structured = str(record.get("ของกลาง (JSON มีโครงสร้าง)", "")).strip()
        categorized = len(structured) > 5
        results.append(
            {
                "recordId": record.get(query_service.COL_RECORD_ID, ""),
                "date": _display_datetime(when),
                "sortKey": _sort_key(when),
                "station": _station_name(record.get(query_service.COL_STATION_ID, "")),
                "unit": record.get(query_service.COL_UNIT_ID, ""),
                "category": record.get("หัวข้อการจับกุม", ""),
                "rawItems": record.get("ของกลาง", ""),
                "isCategorized": categorized,
                "structuredJson": structured if categorized else "[]",
            }
        )

    results.sort(key=lambda item: item["sortKey"], reverse=True)
    return results


def save_evidence(station_id: str, record_id: str, items: Any) -> None:
    """
    เขียน JSON ของกลางที่จัดหมวดหมู่แล้วกลับลงคดี

    รับได้ทั้ง list และสตริง JSON — หน้าเว็บส่ง list มา ส่วนของเดิมส่งสตริง
    """
    payload = items if isinstance(items, str) else json.dumps(items, ensure_ascii=False)
    spreadsheet_id = get_target_db_id(station_id)
    record = query_service.find_record(station_id, "tb_Arrests", record_id)
    worksheet = sheets_service.get_worksheet(spreadsheet_id, "tb_Arrests")
    sheets_service.with_backoff(
        worksheet.update,
        range_name=f"AD{record['_row']}",
        values=[[payload]],
        value_input_option="RAW",
    )
    query_service.invalidate_cache(spreadsheet_id, "tb_Arrests")


# ------------------------------------------------------------- นำขบวน


def escort_data(station_id: str, start: str, end: str) -> Dict[str, Any]:
    """รายการนำขบวนในช่วงวันที่ พร้อมยอดแยกบุคคลสำคัญกับทั่วไป"""
    spreadsheet_id = get_target_db_id(station_id)
    names = _user_names()
    summary = {"vip": 0, "general": 0, "total": 0}
    results: List[Dict[str, Any]] = []

    for record in query_service.cached_rows(spreadsheet_id, ESCORT_TABLE):
        if record.get(query_service.COL_STATUS) != query_service.STATUS_APPROVED:
            continue
        if not query_service.is_active(record.get(query_service.COL_IS_ACTIVE)):
            continue
        when = record.get(query_service.COL_ACTUAL_DATE) or record.get(query_service.COL_TIMESTAMP)
        if not _in_range(when, start, end):
            continue

        kind = str(record.get("ประเภทการนำขบวน", "")).strip()
        if "บุคคลสำคัญ" in kind:
            summary["vip"] += 1
        else:
            summary["general"] += 1
        summary["total"] += 1

        action_by = str(record.get(query_service.COL_ACTION_BY, "")).strip()
        results.append(
            {
                "recordId": record.get(query_service.COL_RECORD_ID, ""),
                "sortKey": _sort_key(when),
                "type": kind,
                "station": _station_name(record.get(query_service.COL_STATION_ID, "")),
                "start": _display_datetime(record.get("วันเวลาเริ่ม")),
                "end": _display_datetime(record.get("วันเวลาสิ้นสุด")),
                "details": record.get("รายละเอียด", ""),
                "fileUrl": record.get("Attachment_Folder", ""),
                "actionBy": names.get(action_by, action_by),
            }
        )

    results.sort(key=lambda item: item["sortKey"], reverse=True)
    return {"records": results, "summary": summary}


def save_escort(
    station_id: str,
    escort_type: str,
    start_datetime: str,
    end_datetime: str,
    details: str,
    action_by: str,
    file_url: str = "",
) -> str:
    """
    บันทึกงานนำขบวนที่ส่วนกลางมอบหมายให้ กก. คืน recordId

    บันทึกเป็น Approved ทันทีเหมือนของเดิม เพราะเป็นคำสั่งจากส่วนกลาง ไม่ใช่รายงาน
    ที่สถานีส่งขึ้นมาให้ตรวจ
    """
    spreadsheet_id = get_target_db_id(station_id)
    now = datetime.now()
    record_id = f"ESC-{station_id}-{now.strftime('%y%m%d-%H%M')}-{now.microsecond % 1000:03d}"
    actual_date = _date_part(start_datetime) or now.strftime("%Y-%m-%d")
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")

    sheets_service.append_report_row(
        spreadsheet_id,
        ESCORT_TABLE,
        [
            record_id, stamp, stamp, action_by, query_service.STATUS_APPROVED, True,
            actual_date, station_id, "ส่วนกลาง Assign",
            escort_type, start_datetime, end_datetime, details, file_url or "ไม่มีไฟล์แนบ",
        ],
    )
    query_service.invalidate_cache(spreadsheet_id, ESCORT_TABLE)
    return record_id


# --------------------------------------------------- รายละเอียดรายวัน


# ตารางที่หน้ารายละเอียดรายวันรวมมาแสดงเรียงตามเวลา พร้อมป้ายประเภท
DETAIL_TABLES: List[Tuple[str, str]] = [
    ("tb_DailyResult", "ผลการปฏิบัติ"),
    ("tb_Arrests", "จับกุม"),
    ("tb_Accidents", "อุบัติเหตุ"),
    ("tb_OtherDuties", "ว.4 อื่นๆ/จิตอาสา"),
    ("tb_RoyalGuard", "รับเสด็จ"),
]


def _detail_text(table: str, record: Dict[str, Any]) -> Tuple[str, str]:
    """สรุปย่อกับลิงก์ไฟล์แนบของแต่ละประเภทรายงาน ตรงกับที่ของเดิมประกอบไว้"""
    if table == "tb_DailyResult":
        return (
            f"ว.43: {record.get('ยอด ว.43', '')}, บริการ: {record.get('ยอด บริการ', '')}, "
            f"ว.42: {record.get('ยอด ว.42', '')}, ว.20: {record.get('ยอด ว.20', '')}\n"
            f"ข้อหา: {record.get('Charges_Detail', '')}",
            record.get("Attachment_Folder", ""),
        )
    if table == "tb_Arrests":
        return (
            f"จับกุม: {record.get('หัวข้อการจับกุม', '')}\n"
            f"ผู้ต้องหา: {record.get('จำนวนผู้ต้องหา', '')} คน\n"
            f"ข้อหา: {record.get('ข้อหาทั้งหมด', '')}\n"
            f"พฤติการณ์: {record.get('พฤติการณ์', '')}",
            record.get("Attachment_Folder", ""),
        )
    if table == "tb_Accidents":
        return (
            f"สถานที่: {record.get('สถานที่เกิดเหตุ', '')}\n"
            f"สาเหตุ: {record.get('สาเหตุ', '')}",
            record.get("Attachment_Folder", ""),
        )
    if table == "tb_OtherDuties":
        return (
            f"การปฏิบัติ: {record.get('การปฏิบัติ', '')}\n"
            f"ดำเนินการ: {record.get('ดำเนินการ', '')}\n"
            f"สถานที่: {record.get('สถานที่', '')}",
            record.get("Attachment_Folder", ""),
        )
    if table == "tb_RoyalGuard":
        stage = "ปล่อยแถว" if record.get("prep=ปล่อยแถว, complete=เสร็จสิ้น") == "prep" else "เสร็จสิ้น"
        return (
            f"ภารกิจ: {record.get('ชื่อภารกิจ', '')}\n"
            f"สถานะ: {stage}\n"
            f"รายละเอียด: {record.get('รายละเอียด หรือ ไทม์ไลน์', '')}",
            record.get("FileUrl", ""),
        )
    return "", ""


def daily_detail(station_id: str, start: str, end: str) -> List[Dict[str, Any]]:
    """
    ทุกรายงานที่อนุมัติแล้วในช่วงวันที่ เรียงตามวันแล้วตามเวลา

    หน้านี้คือที่ ฝอ.กก. ใช้ไล่ดูว่าวันนั้นแต่ละหน่วยทำอะไรไปบ้าง ก่อนสรุปขึ้น กก.
    """
    spreadsheet_id = get_target_db_id(station_id)
    names = _user_names()
    results: List[Dict[str, Any]] = []

    for table, label in DETAIL_TABLES:
        for record in query_service.cached_rows(spreadsheet_id, table):
            if record.get(query_service.COL_STATUS) != query_service.STATUS_APPROVED:
                continue
            if not query_service.is_active(record.get(query_service.COL_IS_ACTIVE)):
                continue
            row_station = record.get(query_service.COL_STATION_ID, "")
            if not query_service.check_station_match(str(station_id), row_station):
                continue
            day = record.get(query_service.COL_ACTUAL_DATE) or record.get(query_service.COL_TIMESTAMP)
            if not _in_range(day, start, end):
                continue

            details, link = _detail_text(table, record)
            reporter = str(record.get(query_service.COL_ACTION_BY, "")).strip()
            when = record.get("วันที่เวลาที่รายงาน") or record.get("วันเวลา") or record.get(query_service.COL_TIMESTAMP)
            results.append(
                {
                    "recordId": record.get(query_service.COL_RECORD_ID, ""),
                    "sheetName": table,
                    "rawDate": _date_part(day),
                    "time": _time_part(when),
                    "type": label,
                    "station": _station_name(row_station),
                    "unit": record.get(query_service.COL_UNIT_ID, ""),
                    "details": details,
                    "reporter": names.get(reporter, reporter),
                    "link": link,
                }
            )

    results.sort(key=lambda item: (item["rawDate"], item["time"]))
    return results


# ------------------------------------------------- หน้าผู้กำกับการ


def executive_overview(station_id: str, start: str, end: str) -> Dict[str, Any]:
    """
    ภาพรวมสำหรับผู้กำกับการ — ผลงานรายสถานีคู่กับกำลังพลที่มีจริง

    ตัวเลขที่ผู้กำกับการดูจริงคือ "ภารกิจเฉลี่ยต่อคน" ไม่ใช่ยอดดิบ เพราะสถานีที่คน
    น้อยกว่าแต่ทำงานเท่ากันคือสถานีที่รับภาระหนักกว่า
    """
    performance = query_service.division_summary(station_id, start, end)
    manpower = manpower_overview(station_id)
    stations = get_division_stations(station_id, include_hq=False)
    per_station = {bucket["station"]: bucket for bucket in performance.get("byStation", [])}

    categories: List[str] = []
    workload = {key: [] for key in ("arrest", "v20", "royalGuard", "volunteer", "mission")}
    staff: List[int] = []
    ratio: List[float] = []

    for sid in stations:
        bucket = per_station.get(sid, {})
        categories.append(f"ส.ทล.{sid[1:]}")
        total_tasks = 0
        for key in workload:
            value = int(bucket.get(key, 0) or 0)
            workload[key].append(value)
            total_tasks += value

        net = int(manpower.get(sid, {}).get("net", 0) or 0)
        staff.append(net)
        ratio.append(round(total_tasks / net, 2) if net else 0.0)

    return {
        "categories": categories,
        "workload": workload,
        "staff": staff,
        "ratio": ratio,
        "totals": performance.get("totals", {}),
        "stations": per_station,
        "manpower": manpower,
    }


def mission_calendar(station_id: str, year_month: str) -> List[Dict[str, Any]]:
    """ภารกิจที่ยัง Active ของเดือนนั้น สำหรับปฏิทินหน้าผู้กำกับการ"""
    spreadsheet_id = get_target_db_id(station_id)
    valid = set(get_division_stations(station_id, include_hq=True)) | {"00"}
    division = station_id[:1]
    results: List[Dict[str, Any]] = []

    for record in query_service.cached_rows(spreadsheet_id, "tb_Missions"):
        if record.get(query_service.COL_STATUS) != "Active":
            continue
        if not query_service.is_active(record.get(query_service.COL_IS_ACTIVE)):
            continue
        start = record.get("วันที่เวลาเริ่มภารกิจ", "")
        if _date_part(start)[:7] != year_month:
            continue

        # รหัสสถานีในตารางภารกิจกรอกกันมาหลายแบบ ("ส.ทล.1", "1", "51") ต้องปรับให้
        # เป็นรหัสสองหลักก่อน ไม่งั้นปฏิทินจะจัดภารกิจไปอยู่ผิดสถานี
        raw = str(record.get(query_service.COL_STATION_ID, "")).strip()
        key = raw.replace("ส.ทล.", "").strip()
        if len(key) == 1:
            key = division + key
        if key not in valid:
            key = "00"

        results.append(
            {
                "recordId": record.get(query_service.COL_RECORD_ID, ""),
                "stationId": key,
                "stationName": _station_name(key) if key != "00" else "ส่วนกลาง",
                "unitId": record.get(query_service.COL_UNIT_ID, ""),
                "startTime": start,
                "endTime": record.get("วันที่เวลาสิ้นสุดภารกิจ") or None,
                "targetUnits": record.get("หน่วยบริการที่เกี่ยวข้อง - เก็บเป็นข้อความคั่นด้วยลูกน้ำ", ""),
                "details": record.get("รายละเอียดภารกิจ", ""),
                "location": record.get("สถานที่", ""),
            }
        )

    results.sort(key=lambda item: _sort_key(item["startTime"]))
    return results


# ------------------------------------------- ตารางแจกแจงเชิงลึก


# หมวดรายงานจับกุมที่หน้าภาพรวมให้เลือกชำแหละ ตรงกับ checkbox ชุด chkContainerArrest
# ของเดิม (hq_dashboard.html บรรทัด 209-218) สี่ตัวแรกติ๊กไว้ให้ตั้งแต่เปิดหน้า
ARREST_CATEGORIES: List[Tuple[str, bool]] = [
    ("ยาเสพติด", True),
    ("จับตามหมายจับ (คดีค้างเก่า)", True),
    ("พ.ร.บ.จราจรทางบก", True),
    ("เมาแล้วขับ", True),
    ("พ.ร.บ.รถยนต์ (ป้ายปลอม/สวมทะเบียน)", False),
    ("อาวุธปืน/เครื่องกระสุน", False),
    ("บุคคลต่างด้าวหลบหนีเข้าเมือง", False),
    ("สินค้าหนีภาษี/ศุลกากร", False),
    ("พ.ร.บ.ป่าไม้/สัตว์ป่า", False),
]

# Charges_Detail เก็บเป็น "ข้อหา (จำนวน) | ข้อหา (จำนวน)" — ดึงชื่อกับจำนวนออกจากกัน
_CHARGE_WITH_COUNT = re.compile(r"^(.*?)\s*\((\d+)\)\s*$")


def detailed_analysis(
    station_id: str,
    start: str,
    end: str,
    mode: str,
    categories: List[str],
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    ตารางแจกแจง "ข้อหา/หมวดจับกุม x สถานี" ของหน้าภาพรวม

    mode = daily_charges  นับจำนวนใบสั่งรายข้อหาจาก Charges_Detail ใน tb_DailyResult
    mode = arrests        นับจำนวนคดีรายหมวดจาก "หัวข้อการจับกุม" ใน tb_Arrests

    เก็บ recordId ของแถวที่นับไว้ในแต่ละช่องด้วย หน้าเว็บใช้ตอนคลิกตัวเลขเพื่อเปิดดู
    ว่ายอดนั้นมาจากใบงานไหนบ้าง
    """
    spreadsheet_id = get_target_db_id(station_id)
    stations = get_division_stations(station_id, include_hq=False)

    breakdown: Dict[str, Dict[str, Dict[str, Any]]] = {
        category: {key: {"count": 0, "ids": []} for key in ["total", *stations]}
        for category in categories
    }
    wanted = set(categories)

    def bump(category: str, station_key: str, amount: int, record_id: str) -> None:
        row = breakdown[category].setdefault(station_key, {"count": 0, "ids": []})
        row["count"] += amount
        if record_id not in row["ids"]:
            row["ids"].append(record_id)
        total = breakdown[category]["total"]
        total["count"] += amount
        if record_id not in total["ids"]:
            total["ids"].append(record_id)

    table = "tb_DailyResult" if mode == "daily_charges" else "tb_Arrests"
    for record in query_service.cached_rows(spreadsheet_id, table):
        if record.get(query_service.COL_STATUS) != query_service.STATUS_APPROVED:
            continue
        if not query_service.is_active(record.get(query_service.COL_IS_ACTIVE)):
            continue
        when = record.get("วันที่เวลาที่รายงาน") or record.get(query_service.COL_ACTUAL_DATE)
        if not _in_range(when, start, end):
            continue

        key = _station_key(record.get(query_service.COL_STATION_ID, ""))
        record_id = record.get(query_service.COL_RECORD_ID, "")

        if mode == "daily_charges":
            raw = str(record.get("Charges_Detail", "")).strip()
            if not raw or raw == "-":
                continue
            for part in raw.split("|"):
                match = _CHARGE_WITH_COUNT.match(part.strip())
                if not match:
                    continue
                name, amount = match.group(1).strip(), int(match.group(2))
                if name in wanted:
                    bump(name, key, amount, record_id)
        else:
            category = str(record.get("หัวข้อการจับกุม", "")).strip()
            if category in wanted:
                bump(category, key, 1, record_id)

    return breakdown


def records_summary(station_id: str, table_name: str, record_ids: List[str]) -> List[Dict[str, Any]]:
    """
    สรุปย่อของใบงานที่ระบุ ใช้ตอนคลิกตัวเลขในตารางแจกแจงเพื่อดูว่ายอดมาจากใบไหน

    คืนเป็นข้อความล้วน ไม่ใช่ HTML เหมือนของเดิม เพราะฝั่ง React ประกอบเองได้และ
    การส่ง HTML ข้ามมาแปลว่าต้อง dangerouslySetInnerHTML ซึ่งเปิดช่อง XSS ฟรี ๆ
    """
    spreadsheet_id = get_target_db_id(station_id)
    wanted = set(record_ids)
    results: List[Dict[str, Any]] = []

    for record in query_service.cached_rows(spreadsheet_id, table_name):
        record_id = record.get(query_service.COL_RECORD_ID, "")
        if record_id not in wanted:
            continue
        if not query_service.check_station_match(str(station_id), record.get(query_service.COL_STATION_ID, "")):
            continue

        if table_name == "tb_Arrests":
            results.append({
                "recordId": record_id,
                "sheetName": table_name,
                "date": _display_datetime(
                    record.get("วันที่เวลาที่ดำเนินการ") or record.get("วันที่เวลาที่รายงาน")
                ),
                "title": f"จับกุม {record.get('หัวข้อการจับกุม', '')}",
                "station": _station_name(record.get(query_service.COL_STATION_ID, "")),
                "unit": record.get(query_service.COL_UNIT_ID, ""),
                "tag": f"{record.get('จำนวนผู้ต้องหา', '0')} คน",
                "tagClass": "bg-danger",
                "charges": record.get("ข้อหาทั้งหมด", ""),
                "detail": record.get("พฤติการณ์", ""),
            })
        else:
            results.append({
                "recordId": record_id,
                "sheetName": table_name,
                "date": _display_datetime(
                    record.get("วันที่เวลาที่รายงาน") or record.get(query_service.COL_TIMESTAMP)
                ),
                "title": "ผลปฏิบัติประจำวัน",
                "station": _station_name(record.get(query_service.COL_STATION_ID, "")),
                "unit": record.get(query_service.COL_UNIT_ID, ""),
                "tag": f"ว.20 : {record.get('ยอด ว.20', '0')} ครั้ง",
                "tagClass": "bg-warning text-dark",
                "charges": str(record.get("Charges_Detail", "")).replace("|", ", "),
                "detail": "",
            })

    return results
