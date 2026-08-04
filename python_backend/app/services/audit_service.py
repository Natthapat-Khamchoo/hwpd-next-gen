"""
HWPD Next Gen - Audit trail service.

ร่องรอยว่าใครทำอะไรกับรายการไหนเมื่อไร ใช้ร่วมกันสามที่: การอนุมัติของแอดมิน (ข้อ 9)
การแก้ไข/ยกเลิกรายการของผู้ปฏิบัติ (ข้อ 10) และทุก action ในโมดูลประชาสัมพันธ์ (FR-05)

**เก็บลงบัฟเฟอร์ระหว่าง request แล้วเขียนทีเดียวตอนจบ** ไม่ได้เขียนทันทีที่เรียก
เพราะระบบนี้ใช้บัญชี Google บัญชีเดียวทั้งระบบและชนโควตา 60 คำขอ/นาที มาแล้ว
การเขียน audit ทุกครั้งที่มี action จะเพิ่มคำขอเป็นเท่าตัวโดยไม่จำเป็น
หนึ่ง request ที่แตะสามรายการจึงกิน 1 คำขอ ไม่ใช่ 3

บัฟเฟอร์ผูกกับ context ของ request ด้วย ContextVar จึงไม่ปนกันระหว่างผู้ใช้ที่ยิงพร้อมกัน

**การเขียน audit ล้มเหลวต้องไม่ทำให้ action ของผู้ใช้ล้มตาม** เพราะตอนที่ flush
รายการหลักถูกบันทึกไปแล้ว การขว้าง error ตอนนั้นจะทำให้ผู้ใช้เห็นว่าล้มเหลว
ทั้งที่ข้อมูลเข้าไปแล้ว แล้วกดซ้ำจนได้ข้อมูลซ้ำ ที่นี่จึงบันทึกเป็น log ระดับ error
พร้อมเนื้อรายการที่เขียนไม่สำเร็จ เพื่อให้ตามเก็บย้อนหลังได้จาก log ของเซิร์ฟเวอร์
"""

import json
import logging
import secrets
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_target_db_id
from app.services import sheets_service

logger = logging.getLogger(__name__)

AUDIT_TABLE = "tb_AuditLog"

# ชนิดของ action ที่บันทึก รวมไว้ที่เดียวเพื่อไม่ให้แต่ละ endpoint ตั้งชื่อกันเอง
# จนตอนออกรายงานแยกไม่ออกว่า "CANCEL" กับ "Canceled" คืออันเดียวกันหรือเปล่า
ACTION_CREATE = "CREATE"
ACTION_UPDATE = "UPDATE"
ACTION_APPROVE = "APPROVE"
ACTION_REJECT = "REJECT"
ACTION_CANCEL = "CANCEL"
ACTION_PUBLISH = "PUBLISH"

KNOWN_ACTIONS = frozenset(
    {ACTION_CREATE, ACTION_UPDATE, ACTION_APPROVE, ACTION_REJECT, ACTION_CANCEL, ACTION_PUBLISH}
)

# (spreadsheet_id, row) ที่รอเขียน
_buffer: ContextVar[Optional[List[Tuple[str, List[Any]]]]] = ContextVar("hwpd_audit_buffer", default=None)


def generate_log_id() -> str:
    """รหัสรายการ audit ไม่ซ้ำแม้เขียนพร้อมกันหลาย request"""
    return "AUD-{}-{:06d}".format(datetime.now().strftime("%Y%m%d%H%M%S"), secrets.randbelow(1000000))


def begin() -> None:
    """เปิดบัฟเฟอร์ใหม่ให้ request นี้ ทิ้งของที่ค้างจาก request ก่อน (ถ้ามี)"""
    _buffer.set([])


def pending() -> int:
    """จำนวนรายการที่รอเขียน ใช้ตรวจในเทสและตอน debug"""
    return len(_buffer.get() or [])


def changed_fields(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    คืนเฉพาะฟิลด์ที่ค่าเปลี่ยน ในรูป {ชื่อฟิลด์: {"from": เดิม, "to": ใหม่}}

    เก็บเฉพาะส่วนต่าง ไม่เก็บทั้งแถว เพราะแถวหนึ่งมีได้ถึง 34 คอลัมน์ ถ้าเก็บหมด
    ตาราง audit จะโตเร็วกว่าตารางข้อมูลจริงหลายเท่า และคนอ่านก็หาไม่เจอว่าอะไรเปลี่ยน
    """
    diff: Dict[str, Dict[str, Any]] = {}
    for key in set(before) | set(after):
        # ฟิลด์ภายในของ query_service ไม่ใช่ข้อมูลจริง ไม่ต้องเก็บ
        if str(key).startswith("_"):
            continue
        old, new = before.get(key), after.get(key)
        if old != new:
            diff[key] = {"from": old, "to": new}
    return diff


def _dump(value: Any) -> str:
    """แปลงเป็น JSON แบบกระชับ ค่าว่างคืนสตริงว่างเพื่อไม่ให้ชีตเต็มไปด้วย {}"""
    if not value:
        return ""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def record(
    session: Dict[str, Any],
    action: str,
    target_table: str,
    target_record_id: str,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    note: str = "",
    station_id: Optional[str] = None,
) -> None:
    """
    ต่อคิวหนึ่งรายการ audit ยังไม่เขียนลงชีตจนกว่าจะเรียก `flush()`

    `station_id` ใส่เมื่อรายการที่ถูกกระทำอยู่คนละสถานีกับคนกด (เช่น ฝอ.กก. อนุมัติ
    ของสถานีลูก) เพราะต้องเขียน log ลงสเปรดชีตของ กก. ที่รายการนั้นอยู่ ไม่ใช่ของคนกด
    """
    if action not in KNOWN_ACTIONS:
        raise ValueError(f"action '{action}' ไม่อยู่ในรายการที่รองรับ ({', '.join(sorted(KNOWN_ACTIONS))})")

    actor_station = str(session.get("s") or "").strip()
    target_station = str(station_id or actor_station).strip()

    try:
        spreadsheet_id = get_target_db_id(target_station)
    except ValueError:
        # กก. ที่ยังไม่ได้ตั้งค่าฐานข้อมูล เขียน log ไม่ได้ แต่ action หลักก็เขียนไม่ได้
        # อยู่แล้ว จึงไม่ใช่กรณีที่ต้องทำให้ request พัง
        logger.warning("ข้าม audit ของสถานี %s เพราะยังไม่ได้ตั้งค่า DB_ROUTER", target_station)
        return

    row = [
        generate_log_id(),
        datetime.now().isoformat(),
        str(session.get("u") or ""),
        str(session.get("r") or ""),
        actor_station,
        action,
        target_table,
        str(target_record_id or ""),
        _dump(before),
        _dump(after),
        note,
    ]

    buffer = _buffer.get()
    if buffer is None:
        # ไม่มีใครเรียก begin() มาก่อน (เช่น เรียกจากสคริปต์หรือ cron) เขียนทันทีแทน
        # ที่จะทิ้งรายการนั้นไปเงียบ ๆ
        _write([(spreadsheet_id, row)])
        return

    buffer.append((spreadsheet_id, row))


def _write(entries: List[Tuple[str, List[Any]]]) -> int:
    """เขียนรายการที่ค้างลงชีต จัดกลุ่มตามสเปรดชีตให้เหลือคำขอเดียวต่อหนึ่ง กก."""
    by_sheet: Dict[str, List[List[Any]]] = {}
    for spreadsheet_id, row in entries:
        by_sheet.setdefault(spreadsheet_id, []).append(row)

    written = 0
    for spreadsheet_id, rows in by_sheet.items():
        try:
            sheets_service.append_report_rows(spreadsheet_id, AUDIT_TABLE, rows)
            written += len(rows)
        except (sheets_service.SheetWriteError, sheets_service.SheetNotConfigured) as exc:
            # เขียน audit ไม่สำเร็จต้องไม่ทำให้ action ของผู้ใช้ล้มตาม แต่ต้องไม่หายเงียบ
            # จึงพ่นเนื้อรายการลง log เซิร์ฟเวอร์ไว้ให้ตามเก็บย้อนหลังได้
            logger.error(
                "เขียน audit log ลง %s ไม่สำเร็จ: %s | รายการที่หาย: %s",
                spreadsheet_id,
                exc,
                _dump(rows),
            )
    return written


def flush() -> int:
    """เขียนทุกรายการที่ค้างแล้วล้างบัฟเฟอร์ คืนจำนวนแถวที่เขียนสำเร็จ"""
    buffer = _buffer.get()
    if not buffer:
        _buffer.set([])
        return 0

    _buffer.set([])
    return _write(buffer)


def discard() -> int:
    """
    ทิ้งรายการที่ค้างโดยไม่เขียน คืนจำนวนที่ทิ้ง

    ใช้เมื่อ action หลักล้มเหลวหลังจากที่เรียก record() ไปแล้ว จะได้ไม่มี audit
    ของสิ่งที่ไม่เคยเกิดขึ้นจริง
    """
    count = pending()
    _buffer.set([])
    return count
