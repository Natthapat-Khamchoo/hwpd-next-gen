"""
แคชสถิติรายวัน/รายสถานีลง `tb_ReportCache` เพื่อไม่ให้การออกรายงานไปสแกนชีตสด

การรวมยอดตามป้ายหมวดต้องเปิด 2 ตาราง x 8 กก. = 16 ครั้งต่อรายงานหนึ่งใบ ระหว่าง
ทดสอบเจอ Google ตอบ 429 แล้ว ถ้ามีคนกดออกรายงานพร้อมกันหลายคนจะล้ม ระบบเดิมแก้
ด้วยชีตนี้เหมือนกัน (buildDailyStatsForDate_ + nightlyReportCacheSync)

รูปแบบแถวตรงกับของเดิม: dateStr | stationId | updatedAt | statsJson

หนึ่งแถวคือสถิติของ (วันที่, สถานี) แถวเดิมของคู่เดียวกันถูกเขียนทับในตำแหน่งเดิม
ไม่ต่อท้าย ไม่งั้นชีตจะโตจนชนเพดานแถวแบบเดียวกับที่ tb_National_Summary เคยเจอ
"""

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.config import MASTER_SHEET_ID, get_db_router
from app.services import query_service, sheets_service, tag_stats_service

logger = logging.getLogger(__name__)

CACHE_TABLE = "tb_ReportCache"
COL_DATE = "dateStr"
COL_STATION = "stationId"
COL_UPDATED = "updatedAt"
COL_STATS = "statsJson"

HEADER = [COL_DATE, COL_STATION, COL_UPDATED, COL_STATS]


def _blank() -> Dict[str, int]:
    return {"cases": 0, "suspects": 0, "citations": 0}


def date_range(start: str, end: str) -> List[str]:
    try:
        first = datetime.strptime(start, "%Y-%m-%d").date()
        last = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        return []
    if last < first:
        return []
    return [(first + timedelta(days=n)).isoformat() for n in range((last - first).days + 1)]


def _read_rows() -> List[Dict[str, Any]]:
    rows = sheets_service.read_table(MASTER_SHEET_ID, CACHE_TABLE)
    if not rows:
        return []
    header = [str(h).strip() for h in rows[0]]
    out = []
    for line, row in enumerate(rows[1:], start=2):
        record = {c: (str(row[i]).strip() if i < len(row) else "") for i, c in enumerate(header)}
        if record.get(COL_DATE):
            record["_row"] = line
            out.append(record)
    return out


def refresh(dates: List[str], divisions: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    สร้างแคชใหม่สำหรับวันที่ที่ระบุ คืนสรุปว่าเขียนทับกี่แถว เพิ่มใหม่กี่แถว

    อ่านชีตสดครั้งเดียวต่อ กก. แล้วกระจายลงทุกวันในช่วง จึงไม่ได้อ่านซ้ำต่อวัน
    """
    if not dates:
        return {"dates": 0, "replaced": 0, "appended": 0}

    start, end = min(dates), max(dates)
    wanted = set(dates)
    targets = divisions or sorted(
        d for d, entry in get_db_router().items() if d != "0" and entry.get("OPS")
    )
    mapping = tag_stats_service.charge_tags()

    fresh: Dict[tuple, Dict[str, Dict[str, int]]] = {}
    for division in targets:
        try:
            per_date = tag_stats_service.aggregate_by_date_station(division, start, end, mapping)
        except Exception as exc:
            logger.warning("สร้างแคชของ กก.%s ไม่ได้: %s", division, exc)
            continue
        for date_key, stations in per_date.items():
            if date_key not in wanted:
                continue
            for station, tags in stations.items():
                fresh[(date_key, station)] = tags

    existing = _read_rows()
    by_key = {(r[COL_DATE], r[COL_STATION]): r for r in existing}
    worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, CACHE_TABLE, ensure=False)
    stamp = datetime.now().isoformat(timespec="seconds")

    updates, appended = [], []
    for (date_key, station), tags in sorted(fresh.items()):
        payload = json.dumps(tags, ensure_ascii=False, separators=(",", ":"))
        row = [date_key, station, stamp, payload]
        match = by_key.get((date_key, station))
        if match:
            updates.append({"range": f"A{match['_row']}:D{match['_row']}", "values": [row]})
        else:
            appended.append(row)

    if updates:
        sheets_service.with_backoff(worksheet.batch_update, updates, value_input_option="RAW")

    if appended:
        first_free = max((r["_row"] for r in existing), default=1) + 1
        last_row = first_free + len(appended) - 1
        # ชีตมีเพดานแถว เขียนเลยขอบไป Google ตอบ 400 แล้วทิ้งทั้ง batch แบบเดียวกับ
        # ที่ tb_National_Summary เคยเจอ ขยายก่อนเขียนเสมอ
        if last_row > worksheet.row_count:
            sheets_service.with_backoff(worksheet.add_rows, last_row - worksheet.row_count + 200)
        sheets_service.with_backoff(
            worksheet.update,
            range_name=f"A{first_free}:D{last_row}",
            values=appended,
            value_input_option="RAW",
        )

    logger.info("แคชรายงาน %s ถึง %s: เขียนทับ %d เพิ่มใหม่ %d",
                start, end, len(updates), len(appended))
    return {"dates": len(dates), "replaced": len(updates), "appended": len(appended)}


def read_range(start: str, end: str) -> Dict[str, Any]:
    """
    อ่านแคชในช่วงวันที่ คืนยอดรวมรายสถานี รายกองกำกับ และรวมทั้งประเทศ

    `missingDates` บอกวันที่ยังไม่มีในแคช ผู้เรียกจะได้รู้ว่ายอดที่ได้ครอบคลุมจริงแค่ไหน
    ไม่ใช่เห็นเลขน้อยแล้วเข้าใจว่าไม่มีผลงาน
    """
    by_station: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(lambda: defaultdict(_blank))
    by_division: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(lambda: defaultdict(_blank))
    total: Dict[str, Dict[str, int]] = defaultdict(_blank)
    seen_dates = set()

    for record in _read_rows():
        date_key = record[COL_DATE][:10]
        if (start and date_key < start) or (end and date_key > end):
            continue
        try:
            stats = json.loads(record.get(COL_STATS) or "{}")
        except json.JSONDecodeError:
            logger.warning("แคชแถว %s เสีย ข้ามไป", record.get("_row"))
            continue
        seen_dates.add(date_key)
        station = record.get(COL_STATION, "")
        division = station[:1]
        for tag, values in stats.items():
            for field in ("cases", "suspects", "citations"):
                number = int(values.get(field, 0) or 0)
                by_station[station][tag][field] += number
                by_division[division][tag][field] += number
                total[tag][field] += number

    wanted = date_range(start, end)
    return {
        "byStation": {s: dict(t) for s, t in by_station.items()},
        "byDivision": {d: dict(t) for d, t in by_division.items()},
        "total": dict(total),
        "cachedDates": sorted(seen_dates),
        "missingDates": [d for d in wanted if d not in seen_dates],
    }
