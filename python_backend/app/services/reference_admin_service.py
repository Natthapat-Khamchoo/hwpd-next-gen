"""
แก้ตารางอ้างอิงในชีตกลาง — ข้อหา / ประเภทของกลาง / รายการรายงาน

เทียบเท่า saveChargeByAdmin, saveSeizedItemTypeByAdmin, saveReportCatalogByAdmin
และคู่ delete ของแต่ละตัวใน Apps Script เดิม สามตารางมีโครงต่างกันแต่วิธีแก้เหมือนกัน
(หาแถวจากคอลัมน์คีย์ แล้วเขียนทับทั้งแถว) จึงรวมเป็นตัวเดียวแทนที่จะเขียนสามชุด

ชื่อตารางมาจากทะเบียนข้างล่างเท่านั้น ไม่รับชื่อชีตจากผู้เรียก ไม่งั้น endpoint เดียวนี้
จะกลายเป็นช่องเขียนทับชีตอะไรก็ได้ในไฟล์กลาง รวมถึง tb_Users
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.config import MASTER_SHEET_ID
from app.services import reference_service, sheets_service

logger = logging.getLogger(__name__)


class ReferenceTableError(RuntimeError):
    """แก้ตารางอ้างอิงไม่ได้"""


# kind ที่ API รับ -> ชีตจริง, คอลัมน์คีย์, คอลัมน์เปิด/ปิดใช้งาน
REFERENCE_TABLES: Dict[str, Dict[str, Any]] = {
    "charges": {
        "table": "tb_Charges",
        "key": "ชื่อข้อหา",
        "active": "isActive",
        "label": "ข้อหา",
    },
    "seized-items": {
        "table": "tb_SeizedItemTypes",
        "key": "itemName",
        "active": "isActive",
        "label": "ประเภทของกลาง",
    },
    # ตารางนี้ไม่มีคอลัมน์ isActive จึงปิดใช้งานรายแถวไม่ได้ ดู set_active()
    "report-catalog": {
        "table": "tb_ReportCatalog",
        "key": "reportKey",
        "active": None,
        "label": "รายการรายงาน",
    },
}


def _spec(kind: str) -> Dict[str, Any]:
    spec = REFERENCE_TABLES.get(kind)
    if not spec:
        raise ReferenceTableError(f"ไม่รู้จักตารางอ้างอิง {kind}")
    return spec


def _read(kind: str):
    spec = _spec(kind)
    rows = sheets_service.read_table(MASTER_SHEET_ID, spec["table"])
    if not rows:
        raise ReferenceTableError(f"ตาราง {spec['table']} ว่างเปล่า")
    header = [str(h).strip() for h in rows[0]]
    if spec["key"] not in header:
        raise ReferenceTableError(f"ตาราง {spec['table']} ไม่มีคอลัมน์ {spec['key']}")
    return spec, header, rows


def list_rows(kind: str) -> List[Dict[str, str]]:
    """ทุกแถวเป็น dict ตามชื่อคอลัมน์ พร้อมเลขแถวไว้อ้างอิงตอนแก้"""
    spec, header, rows = _read(kind)
    out = []
    for line, row in enumerate(rows[1:], start=2):
        record = {c: (str(row[i]).strip() if i < len(row) else "") for i, c in enumerate(header)}
        if not record.get(spec["key"]):
            continue
        record["_row"] = line
        out.append(record)
    return out


def upsert(kind: str, values: Dict[str, str], original_key: Optional[str] = None) -> str:
    """
    เพิ่มแถวใหม่หรือแก้แถวเดิม คืนข้อความผลลัพธ์

    original_key ใช้ตอนเปลี่ยนชื่อคีย์ ถ้าไม่ส่งมาจะถือว่าคีย์ใหม่คือคีย์เดิม
    ค่าที่ไม่ได้ส่งมาจะคงของเดิมไว้ ไม่ถูกล้างเป็นค่าว่าง
    """
    spec, header, rows = _read(kind)
    key_column = spec["key"]
    new_key = str(values.get(key_column, "")).strip()
    if not new_key:
        raise ReferenceTableError(f"กรุณาระบุ{spec['label']}")

    lookup = str(original_key or new_key).strip().lower()
    key_index = header.index(key_column)

    target_line = None
    for line, row in enumerate(rows[1:], start=2):
        current = str(row[key_index]).strip() if key_index < len(row) else ""
        if current.lower() == lookup:
            target_line = line
            existing = row
            break

    # ห้ามเปลี่ยนชื่อไปชนกับแถวอื่นที่มีอยู่แล้ว
    if original_key and new_key.strip().lower() != lookup:
        for line, row in enumerate(rows[1:], start=2):
            current = str(row[key_index]).strip() if key_index < len(row) else ""
            if current.lower() == new_key.lower() and line != target_line:
                raise ReferenceTableError(f"มี{spec['label']} \"{new_key}\" อยู่แล้ว")

    worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, spec["table"], ensure=False)
    last_column = chr(ord("A") + len(header) - 1)

    if target_line is None:
        if original_key:
            raise ReferenceTableError(f"ไม่พบ{spec['label']} \"{original_key}\"")
        # แถวว่างแถวแรกโดยดูคอลัมน์คีย์ ไม่ใช่ append_row เพราะชีตอ้างอิงมักมีข้อมูล
        # ห้อยอยู่คอลัมน์ท้าย ๆ ซึ่งทำให้ Google ข้ามไปต่อท้ายแล้วเว้นแถวว่างกลางตาราง
        last = 1
        for line, row in enumerate(rows[1:], start=2):
            if key_index < len(row) and str(row[key_index]).strip():
                last = line
        target_line = last + 1
        existing = []
        action = "เพิ่ม"
    else:
        action = "แก้"

    new_row = [
        str(values.get(column, existing[i] if i < len(existing) else "")).strip()
        for i, column in enumerate(header)
    ]
    sheets_service.with_backoff(
        worksheet.update,
        range_name=f"A{target_line}:{last_column}{target_line}",
        values=[new_row],
        value_input_option="RAW",
    )

    if spec["table"] == reference_service.CHARGES_TABLE:
        reference_service.reset_cache()

    logger.info("%s%s %s (แถว %d)", action, spec["label"], new_key, target_line)
    return f"{action}{spec['label']} \"{new_key}\" เรียบร้อยแล้ว"


def set_active(kind: str, key: str, active: bool) -> str:
    """
    เปิด/ปิดใช้งานแถว — ใช้แทนการลบ

    ของเดิมลบแถวทิ้งจริง แต่ข้อหาที่ถูกลบไปแล้วยังถูกอ้างอยู่ในรายงานจับกุมเก่า
    การปิดใช้งานทำให้หายจาก dropdown เหมือนกัน (reference_service ซ่อนแถวที่
    isActive เป็น FALSE) โดยที่ข้อมูลเก่ายังตามรอยกลับมาได้และกดเปิดคืนได้
    """
    spec, header, rows = _read(kind)
    if not spec["active"]:
        raise ReferenceTableError(f"ตาราง{spec['label']}ไม่มีคอลัมน์เปิด/ปิดใช้งาน")
    if spec["active"] not in header:
        raise ReferenceTableError(f"ตาราง {spec['table']} ไม่มีคอลัมน์ {spec['active']}")

    key_index = header.index(spec["key"])
    active_column = chr(ord("A") + header.index(spec["active"]))
    needle = str(key or "").strip().lower()

    for line, row in enumerate(rows[1:], start=2):
        current = str(row[key_index]).strip() if key_index < len(row) else ""
        if current.lower() == needle:
            worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, spec["table"], ensure=False)
            sheets_service.with_backoff(
                worksheet.update,
                range_name=f"{active_column}{line}",
                values=[["TRUE" if active else "FALSE"]],
                value_input_option="RAW",
            )
            if spec["table"] == reference_service.CHARGES_TABLE:
                reference_service.reset_cache()
            word = "เปิดใช้งาน" if active else "ปิดใช้งาน"
            logger.info("%s%s %s", word, spec["label"], current)
            return f"{word}{spec['label']} \"{current}\" เรียบร้อยแล้ว"

    raise ReferenceTableError(f"ไม่พบ{spec['label']} \"{key}\"")
