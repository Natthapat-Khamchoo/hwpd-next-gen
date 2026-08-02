"""
HWPD Next Gen - Sheet schema definitions.

หัวคอลัมน์ทั้งหมดคัดลอกมาจากชีตจริง (DB_TEST_กก.1) เพื่อให้สเปรดชีตที่สร้างใหม่
หน้าตาเหมือนของเดิมที่ Apps Script สร้างไว้ ทุกตารางขึ้นต้นด้วย 9 คอลัมน์มาตรฐาน
ตามพิมพ์เขียว:

    A Sys_RecordID   B Sys_Timestamp  C Sys_LastUpdate
    D Sys_ActionBy   E Sys_Status     F Sys_IsActive
    G Data_ActualDate (YYYY-MM-DD)    H Data_StationID  I Data_UnitID

คอลัมน์หลังจากนั้นต้องเรียงตรงกับ `row_data` ที่ `prepare_*` ใน report_service สร้าง
ถ้าไม่ตรง ข้อมูลจะลงผิดช่องโดยไม่มี error — tests/test_schema.py ตรวจข้อนี้ให้

จุดที่ป้ายในชีตเดิมกำกวมและแก้ไว้ตรงนี้ (ตำแหน่งคอลัมน์เท่าเดิม แก้เฉพาะข้อความ
หัวตาราง ซึ่งเป็นคำอธิบายเท่านั้น เพราะทั้ง Apps Script และ Python อ้างอิงด้วย index):
  - tb_DailyReport คอลัมน์ที่ 14 ในชีตเขียน "รถวิทยุตรวจเขต" ซ้ำกับคอลัมน์ 13
    ทั้งที่ข้อมูลที่เขียนลงไปคือชื่อพลขับ
  - tb_Arrests คอลัมน์ที่ 27 ในชีตเขียน "Structured_Items" แต่ทั้ง saveArrestReport
    ใน รหัส.js (บรรทัด 2032) และ prepare_arrest_report เขียนค่า warrantScope ลงช่องนี้
    ตรงตามคอมเมนต์ "AA=ขอบเขตหมาย" ในไฟล์เดียวกัน
  - tb_StationDuty มีคอลัมน์ชื่อ "เบอร์โทร" ซ้ำสามช่อง แยกเป็นเบอร์ของร้อยเวร สิบเวร
    และพนักงานวิทยุตามลำดับที่ saveStationDutyReport เขียนจริง
"""

from typing import Dict, List

SYSTEM_COLUMNS: List[str] = [
    "Sys_RecordID",
    "Sys_Timestamp",
    "Sys_LastUpdate",
    "Sys_ActionBy",
    "Sys_Status",
    "Sys_IsActive",
    "Data_ActualDate",
    "Data_StationID",
    "Data_UnitID",
]

TABLE_COLUMNS: Dict[str, List[str]] = {
    "tb_DailyReport": SYSTEM_COLUMNS
    + [
        "วันเวลาที่รายงาน",
        "ผู้ปฏิบัติหน้าที่ประจำหน่วย (ชื่อและยศ)",
        "เบอร์โทร",
        "รถวิทยุตรวจเขต",
        "พลขับ (ชื่อและยศ)",
        "เบอร์โทรพลขับ",
        "พนักงานวิทยุ (ชื่อและยศ)",
        "เบอร์โทรพงว.",
        "ปฏิบัติหน้าที่ตั้งแต่เวลา",
        "ถึงเวลา",
        "กล้องได้รับทั้งหมด (ตัว)",
        "กล้องพร้อมใช้งาน (ตัว)",
        "กล้องใช้งานไม่ได้ (ตัว)",
        "Attachment_Folder",
    ],
    "tb_Checkpoints": SYSTEM_COLUMNS
    + [
        "วันที่เวลาที่รายงาน",
        "ยศ ชื่อ สกุล ตำแหน่ง ผู้รายงาน",
        "จำนวนผู้ปฏิบัติรวม",
        "รถวิทยุตรวจเขต",
        "สถานที่/จุดตรวจ",
        "Attachment_Folder",
    ],
    "tb_Arrests": SYSTEM_COLUMNS
    + [
        "วันที่เวลาที่รายงาน",
        "หัวข้อการจับกุม",
        "จับโดย",
        "ประเภทการจับกุม",
        "ประเภทหมายจับ",
        "วันที่เวลาที่ดำเนินการ",
        "ชุดจับกุม - เก็บเป็นรายชื่อต่อกันด้วยลูกน้ำ",
        "จำนวนผู้ต้องหา",
        "ข้อมูลผู้ต้องหาทั้งหมด",
        "ข้อหาทั้งหมด",
        "สถานที่จับกุม",
        "ละติจูด",
        "ลองจิจูด",
        "ของกลาง",
        "พฤติการณ์",
        "การดำเนินการส่งต่อ",
        "Attachment_Folder",
        "ขอบเขตหมาย",
        "เลขคดี",
        "ตรวจค้น/แจ้งข้อกล่าวหา",
        "ของกลาง (JSON มีโครงสร้าง)",
        "ประเภทคดีบุหรี่ไฟฟ้า",
        "เว็บไซต์/URL ที่เกี่ยวข้อง",
        "มูลค่าความเสียหาย (บาท)",
        "วงเงินหมุนเวียน (บาท)",
    ],
    "tb_DailyResult": SYSTEM_COLUMNS
    + [
        "วันเวลา",
        "ยอด ว.43",
        "ยอด บริการ",
        "ยอด ว.42",
        "ยอด ว.20",
        "Charges_Detail",
        "กล้องทั้งหมด",
        "กล้องพร้อมใช้",
        "กล้องเสีย",
        "Attachment_Folder",
        "สถิติเพิ่มเติม (JSON: มลพิษ/ตรวจค้น/ต่างด้าว)",
    ],
    "tb_StationDuty": SYSTEM_COLUMNS
    + [
        "วันเวลาที่รายงาน",
        "ร้อยเวร",
        "เบอร์โทรร้อยเวร",
        "สิบเวร",
        "เบอร์โทรสิบเวร",
        "พนักงานวิทยุ",
        "เบอร์โทรพงว.",
        "ตั้งแต่เวลา",
        "ถึงวันที่",
    ],
    "tb_OtherDuties": SYSTEM_COLUMNS
    + [
        "วันที่เวลา",
        "รถวิทยุตรวจเขต",
        "รายชื่อเจ้าหน้าที่ที่รวมเป็นข้อความแล้ว",
        "การปฏิบัติ",
        "ดำเนินการ",
        "สถานที่",
        "Attachment_Folder",
        "รายละเอียดจิตอาสา (JSON)",
    ],
    "tb_Accidents": SYSTEM_COLUMNS
    + [
        "วันที่เวลาเกิดเหตุ",
        "ทล., กม., ตำบล, อำเภอ, จังหวัด",
        "ผู้เสียชีวิต / บาดเจ็บ / รพ.",
        "รถหลัก / คู่กรณี",
        "% สาเหตุ",
        "แนวทางแก้ไข",
        "ความเสียหายของราชการ",
        "รถวิทยุที่ ว.4",
        "หน่วยร่วมปฏิบัติ",
        "รายละเอียดพฤติการณ์",
        "ละติจูด",
        "ลองจิจูด",
        "Attachment_Folder",
        "มูลค่าทรัพย์สินเสียหายรวม (บาท)",
    ],
    "tb_Missions": SYSTEM_COLUMNS
    + [
        "วันที่เวลาที่แจ้ง",
        "วันที่เวลาเริ่มภารกิจ",
        "วันที่เวลาสิ้นสุดภารกิจ",
        "หน่วยบริการที่เกี่ยวข้อง - เก็บเป็นข้อความคั่นด้วยลูกน้ำ",
        "รายละเอียดภารกิจ",
        "สถานที่",
        "Attachment_Folde",
    ],
    "tb_RoyalGuard": SYSTEM_COLUMNS
    + [
        "prep=ปล่อยแถว, complete=เสร็จสิ้น",
        "วันเวลาที่กรอกในฟอร์ม",
        "Commanders",
        "ชื่อภารกิจ",
        "หมายเลขรถวิทยุ",
        "รายละเอียด หรือ ไทม์ไลน์",
        "FileUrl",
        "จำนวนที่หมาย",
    ],
    "tb_FuelOil": SYSTEM_COLUMNS
    + [
        "ประเภทรายการ",
        "วันเวลาที่ทำรายการ",
        "ผู้ดำเนินการ",
        "ทะเบียนรถ",
        "เลขไมล์ปัจจุบัน",
        "จำนวนลิตร",
        "ประเภทน้ำมัน/รถ",
        "ราคาบาท",
        "เลขที่ใบเสร็จ",
        "เลขไมล์ครั้งก่อน",
        "ระยะทางใช้งาน(กม.)",
    ],
    # โควตาน้ำมันรายเดือนที่ ฝอ.กก. ตั้งให้แต่ละสถานี ไม่ใช่รายงาน จึงไม่มี 9 คอลัมน์
    # มาตรฐาน — ตรงตามที่ saveHQFuelQuota สร้างแท็บนี้ขึ้นมาเอง (รหัส.js บรรทัด 3603)
    # QuotaLiters ค้างไว้เป็น 0 เสมอ ของเดิมเลิกใช้แล้วแต่ไม่ได้ลบคอลัมน์ทิ้ง
    "tb_FuelQuota": [
        "MonthYear",
        "StationID",
        "QuotaLiters",
        "QuotaBaht",
        "LastUpdate",
        "ActionBy",
        "QuotaOilLiters",
    ],
    "tb_HQ_Escorts": SYSTEM_COLUMNS
    + [
        "ประเภทการนำขบวน",
        "วันเวลาเริ่ม",
        "วันเวลาสิ้นสุด",
        "รายละเอียด",
        "Attachment_Folder",
    ],
    "tb_Documents": SYSTEM_COLUMNS
    + [
        "Report_DateTime",
        "Doc_Subject",
        "Doc_Type",
        "Sender_Name",
        "Status",
        "Doc_File_Url",
    ],
    # ตารางเดียวที่ไม่ได้ขึ้นต้นด้วย 9 คอลัมน์มาตรฐาน เป็นสรุปยอดที่สถานีส่งให้ กก.
    # ไม่ใช่รายงานรายใบ จึงยกเว้นไว้ตามที่ Apps Script ออกแบบมา
    # อยู่ในชีตกลาง ไม่ใช่ชีตของ กก. — หนึ่งแถวคือยอดของหนึ่ง กก. ในหนึ่งวัน
    # Data_StationID เก็บเลข กก. ("5") ไม่ใช่รหัสสถานี ส่วน Data_UnitID เก็บ "กก.5"
    "tb_National_Summary": SYSTEM_COLUMNS
    + [
        "Sum_Arrests",
        "Sum_V20",
        "Sum_V43",
        "Sum_V42",
        "Sum_Service",
        "Sum_Accidents",
        "Sum_Dead",
        "Sum_Injured",
        "Sum_Volunteer",
        "Sum_RoyalGuard",
        "Sum_Missions",
        "JSON_Arrests_Category",
        "JSON_Charges_Detail",
        "JSON_Accident_Causes",
    ],
    # บัญชีผู้ใช้ อยู่ในชีตกลางไฟล์เดียว ไม่ใช่รายงาน จึงไม่มี 9 คอลัมน์มาตรฐาน
    # คอลัมน์ท้าย ๆ ในชีตจริงมีรายการ Role ห้อยไว้เป็นแหล่งข้อมูลของ dropdown
    # ไม่ใช่ข้อมูลผู้ใช้ — read_rows ข้ามให้เองเพราะคอลัมน์ Username ของแถวนั้นว่าง
    "tb_Users": [
        "Username",
        "Password",
        "FullName",
        "Station_ID",
        "Unit_ID",
        "Role",
        "สถานะไปช่วยราชการ",
        "สถานะมาช่วยราชการ",
        "หมายเหตุ",
        "เบอร์โทร",
        "รหัส",
        "วันที่เริ่มช่วยราชการ",
        "วันที่สิ้นสุดช่วยราชการ",
        "AccountType",
    ],
    "tb_HQ_Summary": [
        "Sys_RecordID",
        "Sys_Timestamp",
        "Data_StationID",
        "Data_ReportDate",
        "Sum_V43",
        "Sum_Service",
        "Sum_V42",
        "Sum_V20",
        "Sum_Charges",
        "Sys_ActionBy",
    ],
}


# ตารางที่ไม่ได้ขึ้นต้นด้วย 9 คอลัมน์มาตรฐาน เพราะไม่ใช่รายงานรายใบ
#   tb_HQ_Summary  ยอดสรุปที่สถานีส่งให้ กก. หนึ่งแถวคือหนึ่งวันของหนึ่งสถานี
#   tb_FuelQuota   โควตาน้ำมันที่ ฝอ. ตั้งให้ หนึ่งแถวคือหนึ่งสถานีในหนึ่งเดือน
#   tb_Users       บัญชีผู้ใช้ หนึ่งแถวคือหนึ่งคน
# ทั้งคู่ไม่มีสถานะรออนุมัติ จึงไม่ต้องมีคอลัมน์ Sys_Status/Sys_IsActive
NON_STANDARD_TABLES = frozenset({"tb_HQ_Summary", "tb_FuelQuota", "tb_Users"})


def get_columns(table_name: str) -> List[str]:
    """คืนหัวคอลัมน์ของตาราง ขว้าง KeyError พร้อมรายชื่อที่รองรับถ้าไม่รู้จัก"""
    try:
        return TABLE_COLUMNS[table_name]
    except KeyError as exc:
        known = ", ".join(sorted(TABLE_COLUMNS))
        raise KeyError(f"ยังไม่ได้นิยาม schema ของตาราง '{table_name}' (ที่รองรับ: {known})") from exc
