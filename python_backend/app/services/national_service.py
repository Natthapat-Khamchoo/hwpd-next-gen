"""
HWPD Next Gen - National rollup.

ภาพรวมทั้งประเทศต้องรวมยอดจาก 8 กก. ซึ่งอยู่คนละสเปรดชีต การอ่านสดทุกครั้งที่
ผู้บังคับการเปิดหน้า dashboard คือ 48 ครั้ง/คำขอ ชนเพดาน 60 ครั้ง/นาทีของ Google
ทันทีที่มีคนเปิดพร้อมกันสองคน

จึงแยกเป็นสองส่วนตามที่ Apps Script ออกแบบไว้:

  aggregate_national()  รวมยอดจากทุก กก. เขียนลง `tb_National_Summary` ในชีตกลาง
                        (รันจาก scripts/aggregate_national.py ด้วย cron)
  national_summary()    อ่านจากตารางนั้นตารางเดียว ใช้ 1 ครั้ง/คำขอ

หนึ่งแถวคือยอดของหนึ่ง กก. ในหนึ่งวัน
"""

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import MASTER_SHEET_ID, get_db_router, get_target_db_id
from app.core.schema import get_columns
from app.services import query_service, sheets_service
from app.services.query_service import (
    COL_ACTUAL_DATE,
    COL_IS_ACTIVE,
    COL_LAST_UPDATE,
    COL_RECORD_ID,
    COL_STATION_ID,
    COL_STATUS,
    COL_TIMESTAMP,
    COL_UNIT_ID,
)

logger = logging.getLogger(__name__)

SUMMARY_TABLE = "tb_National_Summary"

# ชื่อฟิลด์ที่หน้า dashboard ระดับประเทศอ่าน ต่างจากชื่อในระดับ กก.
COUNT_COLUMNS = {
    "arrestsCount": "Sum_Arrests",
    "v20Count": "Sum_V20",
    "v43Count": "Sum_V43",
    "v42Count": "Sum_V42",
    "serviceCount": "Sum_Service",
    "accCount": "Sum_Accidents",
    "deadCount": "Sum_Dead",
    "injuredCount": "Sum_Injured",
    "volCount": "Sum_Volunteer",
    "royalCount": "Sum_RoyalGuard",
    "missionCount": "Sum_Missions",
}

CAUSE_FIELDS = ("human", "vehicle", "road", "env")


def _blank_counts() -> Dict[str, int]:
    return {field: 0 for field in COUNT_COLUMNS}


def _load_json_dict(raw: str) -> Dict[str, int]:
    try:
        value = json.loads(str(raw or "").strip() or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {str(k): query_service._to_int(v) for k, v in value.items()}


# ---------------------------------------------------------------------------
# ฝั่งรวมยอด (cron)
# ---------------------------------------------------------------------------


def _casualties(text: str) -> Tuple[int, int]:
    """
    ช่อง "ผู้เสียชีวิต / บาดเจ็บ / รพ." เขียนเป็น "เสียชีวิต: 1, บาดเจ็บ: 3, รพ.: ..."
    ดึงเฉพาะสองตัวเลขแรกออกมา ถ้ารูปแบบไม่ตรงก็นับเป็นศูนย์แทนที่จะพังทั้งรอบ
    """
    import re

    dead = re.search(r"เสียชีวิต\s*:\s*(\d+)", str(text or ""))
    injured = re.search(r"บาดเจ็บ\s*:\s*(\d+)", str(text or ""))
    return (int(dead.group(1)) if dead else 0, int(injured.group(1)) if injured else 0)


def aggregate_division(division: str, start: str, end: str) -> Dict[str, Dict[str, Any]]:
    """รวมยอดของ กก. เดียว แยกตามวัน คืน {วันที่: ยอด}"""
    spreadsheet_id = get_target_db_id(f"{division}1")
    days: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            **_blank_counts(),
            "arrestTypes": Counter(),
            "charges": Counter(),
            "causes": Counter(),
        }
    )

    tables = query_service.SUMMARY_TABLES + ["tb_Accidents"]
    for table in tables:
        for record in query_service.read_rows(spreadsheet_id, table):
            if not query_service._counted(record) or not query_service._in_range(record, start, end):
                continue

            date_key = record.get(COL_ACTUAL_DATE, "")
            if not date_key:
                continue
            bucket = days[date_key]

            if table == "tb_DailyResult":
                bucket["v43Count"] += query_service._to_int(record.get("ยอด ว.43"))
                bucket["v42Count"] += query_service._to_int(record.get("ยอด ว.42"))
                bucket["v20Count"] += query_service._to_int(record.get("ยอด ว.20"))
                bucket["serviceCount"] += query_service._to_int(record.get("ยอด บริการ"))
                for charge, count in query_service._split_charge_counts(record.get("Charges_Detail", "")):
                    bucket["charges"][charge] += count
            elif table == "tb_Arrests":
                bucket["arrestsCount"] += 1
                arrest_type = str(record.get("ประเภทการจับกุม", "")).strip()
                if arrest_type:
                    bucket["arrestTypes"][arrest_type] += 1
                for charge in query_service._split_charges(record.get("ข้อหาทั้งหมด", "")):
                    bucket["charges"][charge] += 1
            elif table == "tb_RoyalGuard":
                bucket["royalCount"] += 1
            elif table == "tb_OtherDuties":
                if record.get("การปฏิบัติ", "") in query_service.VOLUNTEER_DUTY_TYPES:
                    bucket["volCount"] += 1
            elif table == "tb_Missions":
                bucket["missionCount"] += 1
            elif table == "tb_Accidents":
                bucket["accCount"] += 1
                dead, injured = _casualties(record.get("ผู้เสียชีวิต / บาดเจ็บ / รพ.", ""))
                bucket["deadCount"] += dead
                bucket["injuredCount"] += injured
                query_service._add_causes(record.get("% สาเหตุ", ""), bucket["causes"])

    return dict(days)


def _summary_row(division: str, date_key: str, values: Dict[str, Any], record_id: str) -> List[Any]:
    now = datetime.now().isoformat()
    causes = {field: values["causes"].get(field, 0) for field in CAUSE_FIELDS}
    return [
        record_id,
        now,
        now,
        "SYSTEM_CRON",
        "Active",
        True,
        date_key,
        division,
        f"กก.{division}",
        *[values[field] for field in COUNT_COLUMNS],
        json.dumps(dict(values["arrestTypes"]), ensure_ascii=False, separators=(",", ":")),
        json.dumps(dict(values["charges"]), ensure_ascii=False, separators=(",", ":")),
        json.dumps(causes, ensure_ascii=False, separators=(",", ":")),
    ]


def _configured_divisions() -> List[str]:
    return sorted(
        division
        for division, entry in get_db_router().items()
        if division != "0" and entry.get("OPS")
    )


def aggregate_national(start: str, end: str, divisions: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    รวมยอดทุก กก. ในช่วงวันที่แล้วเขียนลง tb_National_Summary

    แถวของ (วันที่, กก.) ที่มีอยู่แล้วจะถูกเขียนทับในตำแหน่งเดิม ไม่ใช่ต่อท้ายใหม่
    ของเดิมที่ Apps Script เขียนไว้ต่อท้ายทุกรอบจนมีแถวซ้ำของวันเดียวกันหลายสิบแถว
    ซ้ำที่เหลือจะถูกปิด Sys_IsActive ทิ้ง เพื่อไม่ให้ยอดถูกนับซ้ำตอนอ่าน
    """
    targets = divisions or _configured_divisions()
    columns = get_columns(SUMMARY_TABLE)

    fresh: Dict[Tuple[str, str], List[Any]] = {}
    stamp = int(datetime.now().timestamp())
    for division in targets:
        for date_key, values in aggregate_division(division, start, end).items():
            record_id = f"SUM-{division}-{date_key}-{stamp}"
            fresh[(date_key, division)] = _summary_row(division, date_key, values, record_id)

    existing = query_service.read_rows(MASTER_SHEET_ID, SUMMARY_TABLE)
    by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for record in existing:
        if query_service.is_active(record.get(COL_IS_ACTIVE)):
            by_key[(record.get(COL_ACTUAL_DATE, ""), record.get(COL_STATION_ID, ""))].append(record)

    last_column = query_service._column_letter(len(columns) - 1)
    active_column = query_service._column_letter(columns.index(COL_IS_ACTIVE))

    updates: List[Dict[str, Any]] = []
    appended: List[List[Any]] = []
    replaced = deactivated = 0

    for key, row in fresh.items():
        matches = by_key.get(key, [])
        if matches:
            keep = matches[-1]
            updates.append({"range": f"A{keep['_row']}:{last_column}{keep['_row']}", "values": [row]})
            replaced += 1
            for stale in matches[:-1]:
                updates.append({"range": f"{active_column}{stale['_row']}", "values": [[False]]})
                deactivated += 1
        else:
            appended.append(row)

    worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, SUMMARY_TABLE, ensure=False)

    if updates:
        sheets_service.with_backoff(worksheet.batch_update, updates, value_input_option="RAW")

    if appended:
        first_free = max((r["_row"] for r in existing), default=1) + 1
        last_row = first_free + len(appended) - 1
        sheets_service.with_backoff(
            worksheet.update,
            range_name=f"A{first_free}:{last_column}{last_row}",
            values=appended,
            value_input_option="RAW",
        )

    logger.info(
        "รวมยอดระดับประเทศ %s ถึง %s: เขียนทับ %d แถว เพิ่มใหม่ %d แถว ปิดแถวซ้ำ %d แถว",
        start, end, replaced, len(appended), deactivated,
    )
    return {
        "divisions": targets,
        "rows": len(fresh),
        "replaced": replaced,
        "appended": len(appended),
        "deactivated": deactivated,
    }


# ---------------------------------------------------------------------------
# ฝั่งอ่าน (dashboard)
# ---------------------------------------------------------------------------


def national_summary(start: str, end: str) -> Dict[str, Any]:
    """
    ภาพรวมทั้งประเทศจาก tb_National_Summary — อ่านตารางเดียว ไม่แตะชีตของ กก.

    ถ้ามีแถวของ (วันที่, กก.) เดียวกันหลายแถว (ข้อมูลเก่าที่ Apps Script เขียนต่อท้าย
    ไว้ทุกรอบ) จะใช้แถวล่างสุดแถวเดียว ไม่งั้นยอดจะถูกนับซ้ำตามจำนวนรอบที่เคยรัน
    """
    rows = query_service.read_rows(MASTER_SHEET_ID, SUMMARY_TABLE)

    latest: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for record in rows:
        if not query_service.is_active(record.get(COL_IS_ACTIVE)):
            continue
        date_key = record.get(COL_ACTUAL_DATE, "")
        if not date_key or (start and date_key < start) or (end and date_key > end):
            continue
        latest[(date_key, record.get(COL_STATION_ID, ""))] = record

    totals = _blank_counts()
    by_division: Dict[str, Dict[str, Any]] = {}
    trend: Dict[str, Dict[str, int]] = {}
    arrest_types: Counter = Counter()
    charges: Counter = Counter()
    causes: Counter = Counter()

    for (date_key, division), record in sorted(latest.items()):
        bucket = by_division.setdefault(
            division,
            {"div": division, "divName": record.get(COL_UNIT_ID) or f"กก.{division}", **_blank_counts()},
        )
        day = trend.setdefault(date_key, {"arrestsCount": 0, "accCount": 0})

        for field, column in COUNT_COLUMNS.items():
            value = query_service._to_int(record.get(column))
            totals[field] += value
            bucket[field] += value

        day["arrestsCount"] += query_service._to_int(record.get("Sum_Arrests"))
        day["accCount"] += query_service._to_int(record.get("Sum_Accidents"))

        arrest_types.update(_load_json_dict(record.get("JSON_Arrests_Category", "")))
        charges.update(_load_json_dict(record.get("JSON_Charges_Detail", "")))
        causes.update(_load_json_dict(record.get("JSON_Accident_Causes", "")))

    return {
        "totals": totals,
        "byDivision": [by_division[key] for key in sorted(by_division)],
        "trend": [{"date": date, **values} for date, values in sorted(trend.items())],
        "arrestTypeBreakdown": dict(arrest_types.most_common(10)),
        "chargeBreakdown": dict(charges.most_common(10)),
        "accCauseBreakdown": {field: causes.get(field, 0) for field in CAUSE_FIELDS},
    }


def deactivate_duplicates() -> Dict[str, Any]:
    """
    ปิด Sys_IsActive ของแถวซ้ำ เก็บไว้แถวล่างสุดของแต่ละ (วันที่, กก.)

    Apps Script เขียนต่อท้ายทุกครั้งที่ cron ทำงาน ตารางจึงมีแถวของวันเดียวกันสะสม
    ไว้หลายสิบแถว ตัวอ่านหยิบแถวล่างสุดอยู่แล้วจึงไม่ผิด แต่ตารางอ่านยากและโตเรื่อย ๆ
    ล้างด้วยการปิดแทนการลบ เผื่อต้องย้อนดูว่าค่าที่เคยรวมไว้เป็นเท่าไร
    """
    columns = get_columns(SUMMARY_TABLE)
    active_column = query_service._column_letter(columns.index(COL_IS_ACTIVE))
    rows = query_service.read_rows(MASTER_SHEET_ID, SUMMARY_TABLE)

    by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for record in rows:
        if query_service.is_active(record.get(COL_IS_ACTIVE)):
            by_key[(record.get(COL_ACTUAL_DATE, ""), record.get(COL_STATION_ID, ""))].append(record)

    updates = [
        {"range": f"{active_column}{stale['_row']}", "values": [[False]]}
        for matches in by_key.values()
        for stale in matches[:-1]
    ]

    if updates:
        worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, SUMMARY_TABLE, ensure=False)
        sheets_service.with_backoff(worksheet.batch_update, updates, value_input_option="RAW")

    logger.info("ปิดแถวซ้ำใน %s แล้ว %d แถว", SUMMARY_TABLE, len(updates))
    return {"keys": len(by_key), "deactivated": len(updates)}


def default_range(days: int = 7) -> Tuple[str, str]:
    """ช่วงวันที่เริ่มต้นของงาน cron — ย้อนหลัง N วันถึงวันนี้"""
    today = datetime.now().date()
    return ((today - timedelta(days=days - 1)).isoformat(), today.isoformat())
