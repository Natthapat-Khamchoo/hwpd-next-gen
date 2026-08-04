"""
HWPD Next Gen - Reference data service.

ข้อมูลอ้างอิงที่ใช้ร่วมกันทุกสถานี อ่านจาก Master Spreadsheet ด้วย credentials
ชุดเดียวกับที่ใช้เขียนรายงาน ตอนนี้มีแค่รายการข้อหา (`tb_Charges`)

แคชไว้ระยะสั้นเหมือน user_service เพราะทุกฟอร์มจับกุมเรียกใช้ตอนเปิดหน้า
"""

import logging
import threading
import time
from typing import Any, Dict, List

from app.core.config import MASTER_SHEET_ID
from app.services import charge_group_service, sheets_service

logger = logging.getLogger(__name__)

CHARGES_TABLE = "tb_Charges"
CACHE_TTL_SECONDS = 300  # 5 นาที

_cache: Dict[str, Any] = {"charges": None, "detailed": None, "ts": 0.0}
_lock = threading.Lock()


class ReferenceDataUnavailable(RuntimeError):
    """อ่านข้อมูลอ้างอิงจาก Google Sheet ไม่ได้"""


# คอลัมน์ F ของ tb_Charges เก็บกลุ่ม พ.ร.บ. (requirement ข้อ 14) ชีตเดิมไม่มีคอลัมน์นี้
# แถวที่ยังไม่ได้กรอกจะถูกเดากลุ่มจากชื่อข้อหาแทน ดู charge_group_service
_GROUP_COLUMN_INDEX = 5


def _parse_charges(rows: List[List[str]]) -> List[Dict[str, str]]:
    """
    คอลัมน์ A คือชื่อข้อหา คอลัมน์ E (isActive) ว่างไว้ = ยังใช้งานอยู่
    ซ่อนเฉพาะแถวที่เขียน FALSE ไว้ชัดเจน ตรงตามที่ getChargeDropdown ใน JS ทำ

    คืน [{"name":..., "group":...}] — คอลัมน์ F ถ้ามีคนกรอกไว้ชนะการเดาเสมอ
    """
    charges: List[Dict[str, str]] = []
    seen = set()
    for row in rows[1:]:
        name = str(row[0]).strip() if row else ""
        if not name:
            continue
        is_active = str(row[4]).strip().upper() if len(row) > 4 else ""
        if is_active == "FALSE":
            continue
        raw_group = str(row[_GROUP_COLUMN_INDEX]).strip() if len(row) > _GROUP_COLUMN_INDEX else ""
        charges.append({"name": name, "group": charge_group_service.group_of(name, raw_group)})
        seen.add(name)

    # ข้อหาที่ requirement สั่งให้มีในระบบ ผสมเข้าไปถ้าชีตยังไม่มี (ดูเหตุผลใน
    # charge_group_service.BUILTIN_CHARGES) ต่อท้ายเพื่อไม่ให้ลำดับเดิมเปลี่ยน
    for name, group in charge_group_service.BUILTIN_CHARGES.items():
        if name not in seen:
            charges.append({"name": name, "group": group})

    return charges


def get_charges_detailed(force: bool = False) -> List[Dict[str, str]]:
    """
    ข้อหาที่ยังใช้งานอยู่ พร้อมกลุ่ม พ.ร.บ. — [{"name":..., "group":...}]
    ขว้าง ReferenceDataUnavailable ถ้าอ่านชีตไม่ได้
    """
    now = time.time()
    cached = _cache.get("detailed")
    if not force and cached is not None and (now - _cache["ts"]) < CACHE_TTL_SECONDS:
        return cached

    with _lock:
        cached = _cache.get("detailed")
        if not force and cached is not None and (time.time() - _cache["ts"]) < CACHE_TTL_SECONDS:
            return cached

        try:
            rows = sheets_service.read_table(MASTER_SHEET_ID, CHARGES_TABLE)
        except sheets_service.SheetNotConfigured as exc:
            raise ReferenceDataUnavailable(str(exc)) from exc
        except sheets_service.SheetWriteError as exc:
            raise ReferenceDataUnavailable(f"อ่านรายการข้อหาไม่สำเร็จ: {exc}") from exc

        charges = _parse_charges(rows)
        _cache["detailed"] = charges
        _cache["charges"] = [item["name"] for item in charges]
        _cache["ts"] = time.time()
        logger.info("โหลดรายการข้อหาจาก %s แล้ว %d รายการ", CHARGES_TABLE, len(charges))
        return charges


def get_charges(force: bool = False) -> List[str]:
    """
    รายชื่อข้อหาล้วน ๆ ตามเดิม — ฟอร์มที่ยังไม่ต้องการกลุ่มเรียกตัวนี้ได้เหมือนเดิม
    ไม่ได้เปลี่ยนรูปแบบที่คืน เพื่อไม่ให้ผู้เรียกเดิมทั้งหมดต้องแก้ตาม
    """
    return [item["name"] for item in get_charges_detailed(force)]


def reset_cache() -> None:
    """ล้างแคช (ใช้ในเทสและตอนแก้ข้อมูลอ้างอิงในชีต)"""
    with _lock:
        _cache["charges"] = None
        _cache["detailed"] = None
        _cache["ts"] = 0.0
