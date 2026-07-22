"""
HWPD Next Gen - Report Submission Service Engine
Ported from JS (saveDailyReport, saveDailyResult, saveCheckpointReport, saveArrestReport, saveAccidentReport, saveMissionReport, saveRoyalGuardReport, saveFuelAndOilRecord)
"""

import random
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.core.config import get_station_data, get_target_db_id
from app.core.sanitization import sanitize_form_data
from app.services.line_service import push_line_message


def format_thai_date(date_str: str) -> str:
    """แปลง ISO date string เป็นวันที่แบบไทย (เช่น 22/07/2569)"""
    if not date_str:
        return ""
    try:
        parts = date_str.split("T")[0].split("-")
        if len(parts) == 3:
            y, m, d = int(parts[0]), parts[1], parts[2]
            return f"{d}/{m}/{y + 543}"
    except Exception:
        pass
    return date_str


def generate_record_id(prefix: str) -> str:
    """สร้าง Record ID มาตรฐาน (เช่น OP-260722-1318-482)"""
    now = datetime.now()
    timestamp_str = now.strftime("%y%m%d-%H%M")
    rand_suffix = random.randint(100, 999)
    return f"{prefix}-{timestamp_str}-{rand_suffix}"


def prepare_daily_report(form_data: Dict[str, Any], folder_url: str = "ไม่มีไฟล์แนบ") -> Dict[str, Any]:
    """
    เตรียมข้อมูลบันทึกและสร้างข้อความส่ง LINE สำหรับ รายงานประจำวัน (OP)
    เทียบเท่า saveDailyReport ใน JS
    """
    form = sanitize_form_data(form_data)
    record_id = generate_record_id("OP")
    st_data = get_station_data(form.get("stationId", "51"))
    unit_name = str(form.get("unitName", "")).replace("หน่วยบริการฯ", "").replace("หน่วยบริการ", "").strip()

    row_data = [
        record_id,
        datetime.now().isoformat(),
        datetime.now().isoformat(),
        form.get("actionBy", ""),
        "Active",
        True,
        str(form.get("reportDateTime", "")).split("T")[0],
        form.get("stationId", ""),
        form.get("unitId", ""),
        form.get("reportDateTime", ""),
        form.get("dutyOfficer", ""),
        form.get("dutyPhone", ""),
        form.get("carNumber", ""),
        form.get("driverName", ""),
        form.get("driverPhone", ""),
        form.get("radioOpName", ""),
        form.get("radioOpPhone", ""),
        form.get("startTime", ""),
        form.get("endTime", ""),
        form.get("camTotal", 0),
        form.get("camReady", 0),
        form.get("camBroken", 0),
        folder_url,
    ]

    time_part = str(form.get("reportDateTime", "")).split("T")[1] if "T" in str(form.get("reportDateTime", "")) else "08.00"
    message = (
        f"หน่วยบริการ {unit_name}\n"
        f"วันที่ {format_thai_date(form.get('reportDateTime', ''))}\n"
        f"ปฏิบัติหน้าที่ประจำหน่วยบริการ {unit_name}\n"
        f"ยศ ชื่อ สกุล {form.get('dutyOfficer', '')}\n"
        f"โทร {form.get('dutyPhone', '')}\n"
        f"รถวิทยุตรวจเขต {form.get('carNumber', '')}\n"
        f"พลขับ ยศ ชื่อ สกุล {form.get('driverName', '')}\n"
        f"โทร {form.get('driverPhone', '')}\n"
        f"พงว. ยศ ชื่อ สกุล {form.get('radioOpName', '')}\n"
        f"โทร {form.get('radioOpPhone', '')}\n"
        f"ปฏิบัติหน้าที่ตั้งแต่เวลา 08.00 น. ของวันที่ {format_thai_date(form.get('startTime', ''))} "
        f"ถึง 08.00 น. ของวันที่ {format_thai_date(form.get('endTime', ''))}\n\n"
        f"รายงานสถานะการใช้งานกล้องประจำตัว body worn\n"
        f"1. กล้อง body worn ได้รับทั้งหมด {form.get('camTotal', 0)} ตัว\n"
        f"2. เปิดใช้งานทดสอบระบบ เวลา {time_part} น.\n"
        f"พร้อมใช้งาน {form.get('camReady', 0)} ตัว\n"
        f"3. ใช้งานไม่ได้ {form.get('camBroken', 0)} ตัว\n\n"
        f"จึงเรียนมาเพื่อโปรดทราบ\n( {unit_name} )\n( {st_data.get('fullName', '')} )\n\n"
        f"ไฟล์หลักฐาน: {folder_url}"
    )

    return {
        "status": "success",
        "recordId": record_id,
        "targetDbId": get_target_db_id(form.get("stationId", "51")),
        "tableName": "tb_DailyReport",
        "rowData": row_data,
        "lineMessage": message,
        "lineGroupId": st_data.get("lineGroupId", ""),
    }


def prepare_checkpoint_report(form_data: Dict[str, Any], folder_url: str = "ไม่มีไฟล์แนบ") -> Dict[str, Any]:
    """
    เตรียมข้อมูลบันทึกและสร้างข้อความส่ง LINE สำหรับ รายงานด่าน/จุดตรวจ (CHK)
    เทียบเท่า saveCheckpointReport ใน JS
    """
    form = sanitize_form_data(form_data)
    record_id = generate_record_id("CHK")
    st_data = get_station_data(form.get("stationId", "51"))

    location = form.get("locationOther") if form.get("location") == "อื่นๆ" else form.get("location", "")

    row_data = [
        record_id,
        datetime.now().isoformat(),
        datetime.now().isoformat(),
        form.get("actionBy", ""),
        "Active",
        True,
        str(form.get("reportDateTime", "")).split("T")[0],
        form.get("stationId", ""),
        form.get("unitId", ""),
        form.get("reportDateTime", ""),
        form.get("dutyOfficer", ""),
        form.get("totalPersonnel", 1),
        form.get("carNumber", ""),
        location,
        folder_url,
    ]

    message = (
        f'"เรียน ผู้บังคับบัญชา"\n'
        f"กองบัญชาการตำรวจสอบสวนกลาง(CIB)​\n"
        f"โดย {st_data.get('fullName', '')} ({st_data.get('province', '')})\n"
        f"วันนี้ {format_thai_date(form.get('reportDateTime', ''))}\n"
        f"หน่วยบริการฯตำรวจทางหลวง {form.get('unitId', '')}\n"
        f"รถวิทยุ {form.get('carNumber', '')}\n"
        f"{form.get('dutyOfficer', '')} พร้อมพวกรวม {form.get('totalPersonnel', 1)} นาย ตั้ง ว.43 อาญา/จราจร \n"
        f"บริเวณ {location} ผลการปฏิบัติจะรายงานให้ทราบต่อไป\n\n"
        f"จึงเรียนมาเพื่อโปรดทราบ\n“ ({st_data.get('province', '')})\"\n"
        f"ไฟล์แนบ: {folder_url}"
    )

    return {
        "status": "success",
        "recordId": record_id,
        "targetDbId": get_target_db_id(form.get("stationId", "51")),
        "tableName": "tb_Checkpoints",
        "rowData": row_data,
        "lineMessage": message,
        "lineGroupId": st_data.get("lineGroupId", ""),
    }


def prepare_arrest_report(
    form_data: Dict[str, Any],
    team_array: List[str],
    suspect_array: List[Dict[str, Any]],
    charge_array: List[str],
    folder_url: str = "ไม่มีไฟล์แนบ",
) -> Dict[str, Any]:
    """
    เตรียมข้อมูลบันทึกและสร้างข้อความส่ง LINE สำหรับ รายงานจับกุม (ARR)
    เทียบเท่า saveArrestReport ใน JS
    """
    form = sanitize_form_data(form_data)
    team = sanitize_form_data(team_array or [])
    suspects = sanitize_form_data(suspect_array or [])
    charges = sanitize_form_data(charge_array or [])

    record_id = generate_record_id("ARR")
    st_data = get_station_data(form.get("stationId", "51"))

    team_text = ", ".join(team)
    charge_text = "\n".join([f"{i+1}. {c}" for i, c in enumerate(charges)])

    suspect_db_text = ""
    suspect_line_text = ""
    for i, s in enumerate(suspects):
        suspect_db_text += f"คนที่ {i+1}: {s.get('name')} (บัตร: {s.get('idCard')}, สัญชาติ: {s.get('nat')}, อายุ: {s.get('age')}, ที่อยู่: {s.get('address')})\n"
        suspect_line_text += f"ชื่อ {s.get('name')}\nเลขบัตรประจำตัวประชาชน/พาสปอร์ต: {s.get('idCard')}\nสัญชาติ: {s.get('nat')}\nอายุ: {s.get('age')} ปี\nที่อยู่: {s.get('address')}\n\n"

    row_data = [
        record_id,
        datetime.now().isoformat(),
        datetime.now().isoformat(),
        form.get("actionBy", ""),
        "Pending",
        True,
        str(form.get("reportDateTime", "")).split("T")[0],
        form.get("stationId", ""),
        form.get("unitId", ""),
        form.get("reportDateTime", ""),
        form.get("category", ""),
        form.get("arrestBy", ""),
        form.get("arrestType", ""),
        form.get("warrantType", ""),
        form.get("actionDateTime", ""),
        team_text,
        form.get("suspectCount", len(suspects)),
        suspect_db_text,
        charge_text,
        form.get("location", ""),
        form.get("lat", ""),
        form.get("lng", ""),
        form.get("items", ""),
        form.get("circumstances", ""),
        form.get("forwarding", ""),
        folder_url,
        str(form.get("warrantScope", "")).strip(),
        str(form.get("caseNumber", "")).strip(),
        str(form.get("caseMethod", "")).strip(),
        str(form.get("seizedItemsJson", "")).strip(),
        str(form.get("ecigType", "")).strip(),
        str(form.get("relatedUrl", "")).strip(),
        str(form.get("damageValue", "")).strip(),
        str(form.get("turnoverValue", "")).strip(),
    ]

    action_dt = str(form.get("actionDateTime", ""))
    action_date_str = format_thai_date(action_dt.split("T")[0]) if "T" in action_dt else format_thai_date(action_dt)
    action_time_str = action_dt.split("T")[1].replace(":", ".") if "T" in action_dt else ""

    message = (
        f"เรียน ผู้บังคับบัญชา\n"
        f"หน่วยงาน บก.ทล.\n{st_data.get('fullName', '')}\n"
        f"หัวข้อ: จับกุม {form.get('category', '')}\n"
        f"จับโดย: {form.get('arrestBy', '')}\n"
        f"ประเภทการจับกุม: {form.get('arrestType', '')}\n"
        f"วันที่ : {action_date_str}\n"
        f"เวลา: {action_time_str} น.\n"
        f"เจ้าหน้าที่ชุดจับกุม : เจ้าหน้าที่ {st_data.get('fullName', '')}\n"
        f"ประกอบด้วย {team_text}\n"
        f"ข้อมูลผู้ต้องหา:\nจำนวน ผู้ต้องหา: {form.get('suspectCount', len(suspects))} คน\n{suspect_line_text.strip()}\n\n"
        f"ข้อหา: \n{charge_text}\n"
        f"สถานที่จับกุม/เกิดเหตุ: {form.get('location', '')}\n"
        f"ละติจูด : {form.get('lat', '')}\nลองจิจูด : {form.get('lng', '')}\n"
        f"ของกลาง: {form.get('items', '')}\n"
        f"พฤติการณ์ : {form.get('circumstances', '')}\n"
        f"การดำเนินการส่งต่อ : {form.get('forwarding', '')}\n"
        f"ไฟล์แนบ: {folder_url}"
    )

    return {
        "status": "success",
        "recordId": record_id,
        "targetDbId": get_target_db_id(form.get("stationId", "51")),
        "tableName": "tb_Arrests",
        "rowData": row_data,
        "lineMessage": message,
        "lineGroupId": st_data.get("lineGroupId", ""),
    }
