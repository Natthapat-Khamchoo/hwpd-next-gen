"""
HWPD Next Gen - Map points service (requirement ข้อ 4)

รวมพิกัดจากสามตารางให้หน้าแผนที่วางเป็นสามชั้นที่เปิด/ปิดแยกกันได้

    crime       tb_Arrests      จุดจับกุม
    checkpoint  tb_Checkpoints  จุดตั้งด่าน
    accident    tb_Accidents    จุดเกิดอุบัติเหตุ

อ่านทั้งสามตารางด้วย `prefetch` ในคำขอเดียว ไม่ใช่ทีละตาราง เพราะ Google คิดโควตาเป็น
จำนวนคำขอ และระบบนี้ใช้บัญชีเดียวทั้งระบบซึ่งชนเพดาน 60 ครั้ง/นาทีมาแล้ว

**ตัวกรองฐานความผิดมีผลกับชั้นจับกุมเท่านั้น** ด่านกับอุบัติเหตุไม่มีข้อหาผูกอยู่
การเอาตัวกรองนี้ไปตัดสองชั้นนั้นด้วยจะทำให้หมุดหายทั้งที่ไม่เกี่ยวกัน
"""

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.core.config import get_division_stations, get_target_db_id
from app.services import query_service

logger = logging.getLogger(__name__)

# ชั้นแผนที่ -> (ตาราง, คอลัมน์ละติจูด, คอลัมน์ลองจิจูด, ป้ายภาษาไทย)
LAYERS: Dict[str, Tuple[str, str, str, str]] = {
    "crime": ("tb_Arrests", "ละติจูด", "ลองจิจูด", "จุดจับกุม"),
    "checkpoint": ("tb_Checkpoints", "ละติจูด", "ลองจิจูด", "จุดตั้งด่าน"),
    "accident": ("tb_Accidents", "ละติจูด", "ลองจิจูด", "จุดเกิดอุบัติเหตุ"),
}

# นับเฉพาะรายการที่ผ่านการตรวจแล้ว ชุดเดียวกับที่ search_service ใช้
COUNTED_STATUSES = {query_service.STATUS_APPROVED, "Active"}

# กันไม่ให้หน้าเว็บได้ก้อนใหญ่จนวาดไม่ไหว ถ้าชนเพดานจะบอกกลับไปว่าโดนตัด
MAX_POINTS_PER_LAYER = 1000

# ขอบเขตประเทศไทยแบบหลวม ๆ ใช้คัดพิกัดที่พิมพ์ผิดออก เช่น สลับ lat/lng กัน
# หรือกรอกเลขไมล์ลงช่องพิกัด ซึ่งเจอในข้อมูลจริงและทำให้แผนที่ซูมออกไปกลางมหาสมุทร
THAILAND_BOUNDS = {"latMin": 5.0, "latMax": 21.0, "lngMin": 96.0, "lngMax": 106.0}


def parse_coordinate(raw: Any) -> Optional[float]:
    """แปลงค่าพิกัดจากชีตเป็นตัวเลข คืน None ถ้าว่างหรือไม่ใช่ตัวเลข"""
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def within_thailand(lat: float, lng: float) -> bool:
    """พิกัดอยู่ในกรอบประเทศไทยหรือไม่ ใช้คัดค่าที่กรอกผิดออกก่อนส่งให้หน้าแผนที่"""
    return (
        THAILAND_BOUNDS["latMin"] <= lat <= THAILAND_BOUNDS["latMax"]
        and THAILAND_BOUNDS["lngMin"] <= lng <= THAILAND_BOUNDS["lngMax"]
    )


def _charges_of(record: Dict[str, Any]) -> List[str]:
    """รายการข้อหาของใบจับกุมหนึ่งใบ ชีตเก็บรวมไว้ช่องเดียวคั่นด้วยลูกน้ำหรือขีดตั้ง"""
    return query_service._split_charges(str(record.get("ข้อหาทั้งหมด", "") or ""))


def _visible(record: Dict[str, Any], stations: Optional[set], start: str, end: str) -> bool:
    """ผ่านเงื่อนไขพื้นฐาน: อนุมัติแล้ว ยังใช้งานอยู่ อยู่ในสังกัดที่เลือก และในช่วงวันที่"""
    if str(record.get(query_service.COL_STATUS, "")) not in COUNTED_STATUSES:
        return False
    if not query_service.is_active(record.get(query_service.COL_IS_ACTIVE)):
        return False
    if stations is not None and str(record.get(query_service.COL_STATION_ID, "")) not in stations:
        return False

    date_value = str(record.get(query_service.COL_ACTUAL_DATE, "") or "")[:10]
    if start and date_value and date_value < start:
        return False
    if end and date_value and date_value > end:
        return False
    return True


def _title_of(layer: str, record: Dict[str, Any]) -> str:
    """ข้อความบรรทัดแรกของ popup ต่างกันตามชนิดของหมุด"""
    if layer == "crime":
        return str(record.get("หัวข้อการจับกุม", "") or "จับกุม")
    if layer == "checkpoint":
        return str(record.get("สถานที่/จุดตรวจ", "") or "จุดตั้งด่าน")
    return str(record.get("ทล., กม., ตำบล, อำเภอ, จังหวัด", "") or "อุบัติเหตุ")


def _detail_of(layer: str, record: Dict[str, Any]) -> str:
    """บรรทัดรองของ popup ตัดให้สั้นพอเห็นในกล่องเล็ก ๆ"""
    if layer == "crime":
        return " | ".join(_charges_of(record)[:3])
    if layer == "checkpoint":
        return f"ผู้ปฏิบัติ {record.get('จำนวนผู้ปฏิบัติรวม', '-')} นาย รถ {record.get('รถวิทยุตรวจเขต', '-')}"
    return str(record.get("ผู้เสียชีวิต / บาดเจ็บ / รพ.", "") or "")[:120]


def _points_from(
    layer: str,
    rows: Iterable[Dict[str, Any]],
    stations: Optional[set],
    start: str,
    end: str,
    charge: str,
    unit: str,
) -> Tuple[List[Dict[str, Any]], int]:
    """คืน (หมุดของชั้นนี้, จำนวนแถวที่มีพิกัดใช้ไม่ได้) """
    points: List[Dict[str, Any]] = []
    bad_coordinates = 0

    for record in rows:
        if not _visible(record, stations, start, end):
            continue
        if unit and str(record.get(query_service.COL_UNIT_ID, "")) != unit:
            continue
        # ตัวกรองฐานความผิดมีผลกับชั้นจับกุมเท่านั้น ดูเหตุผลในหัวไฟล์
        if charge and layer == "crime" and charge not in _charges_of(record):
            continue

        _, lat_column, lng_column, _ = LAYERS[layer]
        lat = parse_coordinate(record.get(lat_column))
        lng = parse_coordinate(record.get(lng_column))
        if lat is None or lng is None or not within_thailand(lat, lng):
            if lat is not None or lng is not None:
                bad_coordinates += 1
            continue

        points.append(
            {
                "layer": layer,
                "recordId": record.get(query_service.COL_RECORD_ID, ""),
                "lat": lat,
                "lng": lng,
                "date": str(record.get(query_service.COL_ACTUAL_DATE, "") or "")[:10],
                "station": record.get(query_service.COL_STATION_ID, ""),
                "unit": record.get(query_service.COL_UNIT_ID, ""),
                "title": _title_of(layer, record),
                "detail": _detail_of(layer, record),
            }
        )

    points.sort(key=lambda p: str(p.get("date", "")), reverse=True)
    return points[:MAX_POINTS_PER_LAYER], bad_coordinates


def map_points(
    station_id: str,
    start: str = "",
    end: str = "",
    layers: Optional[List[str]] = None,
    charge: str = "",
    unit: str = "",
    station_filter: str = "",
) -> Dict[str, Any]:
    """
    รวมหมุดของทุกชั้นที่ขอ พร้อมจำนวนหมุดแต่ละชั้นไว้ให้หน้าเว็บแสดงบนปุ่มสลับชั้น

    `station_id` คือสถานีของผู้ใช้ ใช้เลือกว่าจะเปิดฐานข้อมูลของ กก. ไหน
    `station_filter` คือสถานีที่ผู้ใช้เลือกกรองบนหน้าจอ ถ้าไม่ระบุจะเห็นทั้ง กก.
    """
    wanted = [name for name in (layers or list(LAYERS)) if name in LAYERS]
    if not wanted:
        wanted = list(LAYERS)

    spreadsheet_id = get_target_db_id(station_id)
    tables = [LAYERS[name][0] for name in wanted]
    # อ่านรวดเดียวก่อน แล้ว cached_rows ข้างล่างจะหยิบจากแคชโดยไม่ยิงซ้ำ
    query_service.prefetch(spreadsheet_id, tables)

    if station_filter:
        stations: Optional[set] = {station_filter}
    else:
        # ระดับ ฝอ.กก. และผู้กำกับการเห็นทุกสถานีในกองตัวเอง ส่วนสถานีเห็นของตัวเอง
        own = str(station_id or "").strip()
        if own.endswith("0"):
            stations = set(get_division_stations(own, include_hq=True))
        else:
            stations = {own}

    points: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    skipped = 0

    for name in wanted:
        table = LAYERS[name][0]
        try:
            rows = query_service.cached_rows(spreadsheet_id, table)
        except Exception as exc:
            # ตารางเดียวอ่านไม่ได้ไม่ควรทำให้ทั้งแผนที่ว่าง ของเดิมในการค้นหาก็ทำแบบนี้
            logger.warning("อ่าน %s สำหรับแผนที่ไม่ได้ ข้ามชั้นนี้: %s", table, exc)
            counts[name] = 0
            continue

        layer_points, bad = _points_from(name, rows, stations, start, end, charge, unit)
        counts[name] = len(layer_points)
        skipped += bad
        points.extend(layer_points)

    return {
        "points": points,
        "counts": counts,
        # จำนวนรายการที่มีค่าในช่องพิกัดแต่ใช้ไม่ได้ (พิมพ์ผิด/นอกกรอบประเทศไทย)
        # ส่งกลับไปให้หน้าเว็บบอกผู้ใช้ ไม่ใช่ซ่อนไว้เงียบ ๆ
        "skippedInvalidCoordinates": skipped,
    }
