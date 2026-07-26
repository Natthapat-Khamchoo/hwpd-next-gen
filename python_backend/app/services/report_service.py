"""
HWPD Next Gen - Report Submission Service Engine
Ported from JS (saveDailyReport, saveDailyResult, saveCheckpointReport, saveArrestReport, saveAccidentReport, saveMissionReport, saveRoyalGuardReport, saveFuelAndOilRecord)
"""

import json
import secrets
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
    """
    สร้าง Record ID มาตรฐาน (เช่น OP-260722-131845-4821)

    เดิมใช้แค่ระดับนาที + สุ่ม 3 หลัก ซึ่งชนกันได้จริง: ตอนทดสอบส่งรายงานจาก 8 กก.
    ในนาทีเดียวกัน มีสองใบได้รหัสเดียวกัน ถ้าเกิดกับสองใบในชีตเดียวกัน การอนุมัติหรือ
    ยกเลิกที่อ้างอิงด้วยรหัสจะไปโดนใบผิด

    จึงเพิ่มวินาทีและขยายเลขสุ่มเป็น 6 หลัก ทำให้โอกาสชนของรายงาน 8 ใบที่ส่งพร้อมกัน
    ในวินาทีเดียวลดจาก 3.6% เหลือประมาณ 0.003%
    """
    timestamp_str = datetime.now().strftime("%y%m%d-%H%M%S")
    rand_suffix = secrets.randbelow(1000000)
    return f"{prefix}-{timestamp_str}-{rand_suffix:06d}"


def prepare_daily_report(
    form_data: Dict[str, Any],
    folder_url: str = "ไม่มีไฟล์แนบ",
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    เตรียมข้อมูลบันทึกและสร้างข้อความส่ง LINE สำหรับ รายงานประจำวัน (OP)
    เทียบเท่า saveDailyReport ใน JS
    """
    form = sanitize_form_data(form_data)
    record_id = record_id or generate_record_id("OP")
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


def prepare_checkpoint_report(
    form_data: Dict[str, Any],
    folder_url: str = "ไม่มีไฟล์แนบ",
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    เตรียมข้อมูลบันทึกและสร้างข้อความส่ง LINE สำหรับ รายงานด่าน/จุดตรวจ (CHK)
    เทียบเท่า saveCheckpointReport ใน JS
    """
    form = sanitize_form_data(form_data)
    record_id = record_id or generate_record_id("CHK")
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
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    เตรียมข้อมูลบันทึกและสร้างข้อความส่ง LINE สำหรับ รายงานจับกุม (ARR)
    เทียบเท่า saveArrestReport ใน JS
    """
    form = sanitize_form_data(form_data)
    team = sanitize_form_data(team_array or [])
    suspects = sanitize_form_data(suspect_array or [])
    charges = sanitize_form_data(charge_array or [])

    record_id = record_id or generate_record_id("ARR")
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


# ค่าสถิติเพิ่มเติมของรายงานผลประจำวัน เก็บรวมเป็น JSON คอลัมน์เดียว
# (ตรงกับ DAILY_EXTRA_STAT_KEYS ใน รหัส.js บรรทัด 1618)
DAILY_EXTRA_STAT_KEYS = [
    "smkTransCheck", "smkTransFail", "smkTransCancel",
    "smkBusCheck", "smkBusFail", "smkBusCancel",
    "smkCarCheck", "smkCarFail", "smkCarCancel",
    "smkBikeCheck", "smkBikeFail", "smkBikeCancel",
    "smkArrest", "smkAdvice",
    "burnForestCheck", "burnForestArrest", "burnForestAdvice",
    "burnFarmCheck", "burnFarmArrest", "burnFarmAdvice",
    "factoryCheck", "factoryArrest", "factoryAdvice",
    "searchTarget", "searchSeized", "complaintCount",
    "homeCheck", "vehicleCheck", "alienRecord",
]

VOLUNTEER_TEXT_KEYS = ["volType", "volSubType", "volSpecial", "volHost", "volHostUnit"]
VOLUNTEER_COUNT_KEYS = ["volPolice", "volPoliceOther", "volGov", "volCivil", "volBloodCc", "volPlateletUnit"]


def _date_part(value: Any) -> str:
    """ตัดเอาเฉพาะส่วนวันที่ (YYYY-MM-DD) ออกจากค่า datetime-local"""
    return str(value or "").split("T")[0]


def _int_or_zero(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _system_columns(record_id: str, form: Dict[str, Any], status: str, actual_date: str) -> List[Any]:
    """9 คอลัมน์มาตรฐานที่ทุกตารางขึ้นต้นเหมือนกัน"""
    now = datetime.now().isoformat()
    return [
        record_id,
        now,
        now,
        form.get("actionBy", ""),
        status,
        True,
        actual_date,
        form.get("stationId", ""),
        form.get("unitId", ""),
    ]


def prepare_daily_result(
    form_data: Dict[str, Any],
    charges: Optional[List[Any]] = None,
    folder_url: str = "ไม่มีไฟล์แนบ",
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """ผลการปฏิบัติประจำวัน (RST) เทียบเท่า saveDailyResult ใน JS"""
    form = sanitize_form_data(form_data)
    charge_list = sanitize_form_data(charges or [])
    record_id = record_id or generate_record_id("RST")
    st_data = get_station_data(form.get("stationId", "51"))

    charges_text = "-"
    if charge_list:
        charges_text = " | ".join(
            f"{c.get('name')} ({c.get('amount')})" if isinstance(c, dict) else str(c) for c in charge_list
        )

    extra = {k: _int_or_zero(form.get(k)) for k in DAILY_EXTRA_STAT_KEYS if _int_or_zero(form.get(k)) > 0}
    extra_json = json.dumps(extra, ensure_ascii=False, separators=(",", ":")) if extra else ""

    row_data = _system_columns(record_id, form, "Pending", _date_part(form.get("reportDateTime"))) + [
        form.get("reportDateTime", ""),
        form.get("v43", 0),
        form.get("service", 0),
        form.get("v42", 0),
        form.get("v20", 0),
        charges_text,
        form.get("camTotal2", 0),
        form.get("camReady2", 0),
        form.get("camBroken2", 0),
        folder_url,
        extra_json,
    ]

    message = (
        f"เรียน ผู้บังคับบัญชา\n{st_data.get('fullName', '')}\n"
        f"หน่วยบริการฯ {form.get('unitId', '')}\n"
        f"วันที่ {format_thai_date(form.get('reportDateTime', ''))}\n\n"
        f"ผลการปฏิบัติประจำวัน\n"
        f"ว.43 จำนวน {form.get('v43', 0)} ราย\n"
        f"บริการประชาชน {form.get('service', 0)} ราย\n"
        f"ว.42 จำนวน {form.get('v42', 0)} ราย\n"
        f"ว.20 จำนวน {form.get('v20', 0)} ราย\n"
        f"ข้อหาที่ดำเนินการ: {charges_text}\n\n"
        f"กล้อง body worn ทั้งหมด {form.get('camTotal2', 0)} ตัว "
        f"พร้อมใช้ {form.get('camReady2', 0)} ตัว ใช้ไม่ได้ {form.get('camBroken2', 0)} ตัว\n\n"
        f"จึงเรียนมาเพื่อโปรดทราบ\nไฟล์หลักฐาน: {folder_url}"
    )

    return {
        "status": "success",
        "recordId": record_id,
        "targetDbId": get_target_db_id(form.get("stationId", "51")),
        "tableName": "tb_DailyResult",
        "rowData": row_data,
        "lineMessage": message,
        "lineGroupId": st_data.get("lineGroupId", ""),
    }


def prepare_station_duty(
    form_data: Dict[str, Any],
    folder_url: str = "ไม่มีไฟล์แนบ",
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """ยอดเวรประจำสถานี (STD) เทียบเท่า saveStationDutyReport ใน JS"""
    form = sanitize_form_data(form_data)
    record_id = record_id or generate_record_id("STD")
    st_data = get_station_data(form.get("stationId", "51"))

    # ของเดิมใช้ startTime เป็น Data_ActualDate ไม่ใช่ reportDateTime
    row_data = _system_columns(record_id, form, "Active", _date_part(form.get("startTime"))) + [
        form.get("reportDateTime", ""),
        form.get("inspectorName", ""),
        form.get("inspectorPhone", ""),
        form.get("dutyOfficerName", ""),
        form.get("dutyOfficerPhone", ""),
        form.get("radioOpName", ""),
        form.get("radioOpPhone", ""),
        form.get("startTime", ""),
        form.get("endTime", ""),
    ]

    message = (
        f"เรียน ผู้บังคับบัญชา\n{st_data.get('fullName', '')}\n"
        f"รายงานยอดเวรประจำสถานี\n"
        f"วันที่ {format_thai_date(form.get('reportDateTime', ''))}\n\n"
        f"ร้อยเวร {form.get('inspectorName', '')} โทร {form.get('inspectorPhone', '')}\n"
        f"สิบเวร {form.get('dutyOfficerName', '')} โทร {form.get('dutyOfficerPhone', '')}\n"
        f"พนักงานวิทยุ {form.get('radioOpName', '')} โทร {form.get('radioOpPhone', '')}\n"
        f"ปฏิบัติหน้าที่ตั้งแต่ {format_thai_date(form.get('startTime', ''))} "
        f"ถึง {format_thai_date(form.get('endTime', ''))}\n\n"
        f"จึงเรียนมาเพื่อโปรดทราบ"
    )

    return {
        "status": "success",
        "recordId": record_id,
        "targetDbId": get_target_db_id(form.get("stationId", "51")),
        "tableName": "tb_StationDuty",
        "rowData": row_data,
        "lineMessage": message,
        "lineGroupId": st_data.get("lineGroupId", ""),
    }


def prepare_other_duty(
    form_data: Dict[str, Any],
    officers: Optional[List[Any]] = None,
    folder_url: str = "ไม่มีไฟล์แนบ",
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """ภารกิจอื่น / จิตอาสา (OTH) เทียบเท่า saveOtherDutyReport ใน JS"""
    form = sanitize_form_data(form_data)
    officer_list = sanitize_form_data(officers or [])
    record_id = record_id or generate_record_id("OTH")
    st_data = get_station_data(form.get("stationId", "51"))

    officers_text = "  ".join(f"{i + 1}. {name}" for i, name in enumerate(officer_list))
    duty_type = form.get("dutyType", "")
    duty_display = form.get("dutyOtherText", "") if duty_type == "อื่นๆ" else duty_type
    sys_status = "Pending" if duty_type in ("ทำจิตอาสา", "ว.4 ช่วยเหลือประชาชน") else "Active"

    vol_detail: Dict[str, Any] = {}
    for key in VOLUNTEER_TEXT_KEYS:
        value = str(form.get(key, "") or "").strip()
        if value:
            vol_detail[key] = value
    for key in VOLUNTEER_COUNT_KEYS:
        value = _int_or_zero(form.get(key))
        if value > 0:
            vol_detail[key] = value
    vol_json = (
        json.dumps(vol_detail, ensure_ascii=False, separators=(",", ":"))
        if duty_type == "ทำจิตอาสา" and vol_detail
        else ""
    )

    row_data = _system_columns(record_id, form, sys_status, _date_part(form.get("reportDateTime"))) + [
        form.get("reportDateTime", ""),
        form.get("carNumber", ""),
        officers_text,
        duty_display,
        form.get("actionDetails", ""),
        form.get("location", ""),
        folder_url,
        vol_json,
    ]

    message = (
        f"เรียน ผู้บังคับบัญชา\n{st_data.get('fullName', '')}\n"
        f"หน่วยบริการฯ {form.get('unitId', '')}\n"
        f"วันที่ {format_thai_date(form.get('reportDateTime', ''))}\n\n"
        f"การปฏิบัติ: {duty_display}\n"
        f"รถวิทยุ {form.get('carNumber', '')}\n"
        f"เจ้าหน้าที่ผู้ปฏิบัติ {officers_text}\n"
        f"รายละเอียด: {form.get('actionDetails', '')}\n"
        f"สถานที่: {form.get('location', '')}\n\n"
        f"จึงเรียนมาเพื่อโปรดทราบ\nไฟล์แนบ: {folder_url}"
    )

    return {
        "status": "success",
        "recordId": record_id,
        "targetDbId": get_target_db_id(form.get("stationId", "51")),
        "tableName": "tb_OtherDuties",
        "rowData": row_data,
        "lineMessage": message,
        "lineGroupId": st_data.get("lineGroupId", ""),
    }


def prepare_accident_report(
    form_data: Dict[str, Any],
    folder_url: str = "ไม่มีไฟล์แนบ",
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """รายงานอุบัติเหตุ (ACC) เทียบเท่า saveAccidentReport ใน JS"""
    form = sanitize_form_data(form_data)
    record_id = record_id or generate_record_id("ACC")
    st_data = get_station_data(form.get("stationId", "51"))

    loc_text = (
        f"ทล.{form.get('route', '')} กม.{form.get('km', '')} "
        f"({form.get('direction', '')}) {form.get('locDetails', '')}"
    )
    cas_text = (
        f"ตาย: {form.get('deadCount', '')}, เจ็บ: {form.get('injuredCount', '')}, "
        f"รพ.: {form.get('hospital', '')}"
    )
    veh_text = f"รถหลัก: {form.get('mainVehicle', '')}, คู่กรณี: {form.get('oppVehicle', '')}"
    cause_text = (
        f"คน:{form.get('cHuman', '')}%, รถ:{form.get('cVehicle', '')}%, "
        f"ถนน:{form.get('cRoad', '')}%, แวดล้อม:{form.get('cEnv', '')}%"
    )

    row_data = _system_columns(record_id, form, "Pending", _date_part(form.get("reportDateTime"))) + [
        form.get("reportDateTime", ""),
        loc_text,
        cas_text,
        veh_text,
        cause_text,
        form.get("solutions", ""),
        form.get("govDamage", ""),
        form.get("carNumber", ""),
        form.get("jointUnits", ""),
        form.get("description", ""),
        form.get("lat", ""),
        form.get("lng", ""),
        folder_url,
        str(form.get("propDamageValue", "")).strip(),
    ]

    message = (
        f"เรียน ผู้บังคับบัญชา\n{st_data.get('fullName', '')}\n"
        f"รายงานอุบัติเหตุ\n"
        f"วันที่เกิดเหตุ {format_thai_date(form.get('reportDateTime', ''))}\n"
        f"สถานที่: {loc_text}\n"
        f"ผู้บาดเจ็บเสียชีวิต: {cas_text}\n"
        f"ยานพาหนะ: {veh_text}\n"
        f"สาเหตุ: {cause_text}\n"
        f"แนวทางแก้ไข: {form.get('solutions', '')}\n"
        f"ความเสียหายของราชการ: {form.get('govDamage', '')}\n"
        f"รถวิทยุที่ ว.4: {form.get('carNumber', '')}\n"
        f"หน่วยร่วมปฏิบัติ: {form.get('jointUnits', '')}\n"
        f"พฤติการณ์: {form.get('description', '')}\n"
        f"ละติจูด {form.get('lat', '')} ลองจิจูด {form.get('lng', '')}\n\n"
        f"จึงเรียนมาเพื่อโปรดทราบ\nไฟล์แนบ: {folder_url}"
    )

    return {
        "status": "success",
        "recordId": record_id,
        "targetDbId": get_target_db_id(form.get("stationId", "51")),
        "tableName": "tb_Accidents",
        "rowData": row_data,
        "lineMessage": message,
        "lineGroupId": st_data.get("lineGroupId", ""),
    }


def prepare_mission_report(
    form_data: Dict[str, Any],
    selected_units: Optional[List[str]] = None,
    folder_url: str = "ไม่มีไฟล์แนบ",
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """แจ้งภารกิจ (MIS) เทียบเท่า saveMissionReport ใน JS"""
    form = sanitize_form_data(form_data)
    units = sanitize_form_data(selected_units or [])
    record_id = record_id or generate_record_id("MIS")
    st_data = get_station_data(form.get("stationId", "51"))

    units_text = ", ".join(units)

    row_data = _system_columns(record_id, form, "Active", _date_part(form.get("reportDateTime"))) + [
        form.get("reportDateTime", ""),
        form.get("startTime", ""),
        form.get("endTime", ""),
        units_text,
        form.get("missionDetails", ""),
        form.get("location", ""),
        folder_url,
    ]

    message = (
        f"เรียน ผู้บังคับบัญชา\n{st_data.get('fullName', '')}\n"
        f"แจ้งภารกิจ\n"
        f"วันที่แจ้ง {format_thai_date(form.get('reportDateTime', ''))}\n"
        f"เริ่มภารกิจ {format_thai_date(form.get('startTime', ''))} "
        f"ถึง {format_thai_date(form.get('endTime', ''))}\n"
        f"หน่วยที่เกี่ยวข้อง: {units_text}\n"
        f"รายละเอียด: {form.get('missionDetails', '')}\n"
        f"สถานที่: {form.get('location', '')}\n\n"
        f"จึงเรียนมาเพื่อโปรดทราบ\nไฟล์แนบ: {folder_url}"
    )

    return {
        "status": "success",
        "recordId": record_id,
        "targetDbId": get_target_db_id(form.get("stationId", "51")),
        "tableName": "tb_Missions",
        "rowData": row_data,
        "lineMessage": message,
        "lineGroupId": st_data.get("lineGroupId", ""),
    }


def prepare_royal_guard_report(
    form_data: Dict[str, Any],
    folder_url: str = "ไม่มีไฟล์แนบ",
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """รายงานถวายความปลอดภัย (RG) เทียบเท่า saveRoyalGuardReport ใน JS"""
    form = sanitize_form_data(form_data)
    record_id = record_id or generate_record_id("RG")
    st_data = get_station_data(form.get("stationId", "51"))

    row_data = _system_columns(record_id, form, "Pending", _date_part(form.get("reportDateTime"))) + [
        form.get("reportType", ""),
        form.get("reportDateTime", ""),
        form.get("commanders", ""),
        form.get("missionName", ""),
        form.get("carNumbers", ""),
        form.get("details", ""),
        folder_url,
        form.get("targetCount", ""),
    ]

    report_time = str(form.get("reportDateTime", ""))
    time_str = report_time.split("T")[1].replace(":", ".") if "T" in report_time else ""
    stage = "ปล่อยแถว" if form.get("reportType") == "prep" else "เสร็จสิ้นภารกิจ"

    message = (
        f"เรียน ผู้บังคับบัญชา\n"
        f"{st_data.get('province', '')} : รายงานภารกิจถวายความปลอดภัย {form.get('missionName', '')}\n"
        f"วันนี้ {format_thai_date(form.get('reportDateTime', ''))}\n"
        f"เวลา {time_str} น. ({stage})\n"
        f"ผู้ควบคุม: {form.get('commanders', '')}\n"
        f"รถวิทยุ: {form.get('carNumbers', '')}\n"
        f"จำนวนที่หมาย: {form.get('targetCount', '')}\n"
        f"รายละเอียด: {form.get('details', '')}\n\n"
        f"จึงเรียนมาเพื่อโปรดทราบ\nไฟล์แนบ: {folder_url}"
    )

    return {
        "status": "success",
        "recordId": record_id,
        "targetDbId": get_target_db_id(form.get("stationId", "51")),
        "tableName": "tb_RoyalGuard",
        "rowData": row_data,
        "lineMessage": message,
        "lineGroupId": st_data.get("lineGroupId", ""),
    }


def prepare_fuel_record(
    form_data: Dict[str, Any],
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    บันทึกน้ำมันเชื้อเพลิง / น้ำมันเครื่อง (FUEL) เทียบเท่า saveFuelAndOilRecord ใน JS

    ของเดิมสร้างรหัสจากจำนวนแถวในชีต (lastRow) ซึ่งชนกันได้เมื่อมีคนบันทึกพร้อมกัน
    ตรงนี้ใช้ตัวสร้างรหัสมาตรฐานแทน
    """
    form = sanitize_form_data(form_data)
    record_id = record_id or generate_record_id("FUEL")
    st_data = get_station_data(form.get("stationId", "51"))

    is_refuel = form.get("recordType") == "เติมน้ำมัน"
    action_dt = str(form.get("actionDateTime", "")).replace("T", " ")

    detail = [
        form.get("recordType", ""),
        action_dt,
        form.get("actionPerson", ""),
        form.get("plateNumber", ""),
        form.get("currentMileage", ""),
        form.get("liters", ""),
        form.get("fuelType", "") if is_refuel else form.get("carType", ""),
        form.get("totalPrice", "") if is_refuel else "",
        form.get("receiptNumber", "") if is_refuel else "",
        "" if is_refuel else form.get("prevMileage", ""),
        "" if is_refuel else form.get("distanceUsed", ""),
    ]

    row_data = _system_columns(record_id, form, "Pending", _date_part(form.get("actionDateTime"))) + detail

    return {
        "status": "success",
        "recordId": record_id,
        "targetDbId": get_target_db_id(form.get("stationId", "51")),
        "tableName": "tb_FuelOil",
        "rowData": row_data,
        # ของเดิมไม่ได้ส่ง LINE สำหรับรายการน้ำมัน
        "lineMessage": "",
        "lineGroupId": "",
        "stationName": st_data.get("fullName", ""),
    }


def prepare_document_record(
    form_data: Dict[str, Any],
    folder_url: str = "ไม่มีไฟล์แนบ",
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """ส่งเอกสารเข้าระบบ (DOC) เทียบเท่า saveDocumentRecord ใน JS"""
    form = sanitize_form_data(form_data)
    record_id = record_id or generate_record_id("DOC")
    st_data = get_station_data(form.get("stationId", "51"))

    row_data = _system_columns(record_id, form, "รอลงนาม", _date_part(form.get("reportDateTime"))) + [
        form.get("reportDateTime", ""),
        form.get("subject", ""),
        form.get("docType", ""),
        form.get("senderName", ""),
        "รอลงนาม",
        folder_url,
    ]

    return {
        "status": "success",
        "recordId": record_id,
        "targetDbId": get_target_db_id(form.get("stationId", "51")),
        "tableName": "tb_Documents",
        "rowData": row_data,
        # ของเดิมไม่ได้ส่ง LINE สำหรับงานสารบรรณ
        "lineMessage": "",
        "lineGroupId": "",
        "stationName": st_data.get("fullName", ""),
    }
