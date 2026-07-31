"""
ลบแถวที่ถูกปิด (`Sys_IsActive` เป็นเท็จ) ออกจาก `tb_National_Summary` จริง ๆ

ต่างจาก `aggregate_national.py --dedupe` ตรงที่นั่นแค่ตั้ง `Sys_IsActive=False`
แถวยังอยู่และยังกินพื้นที่ของชีตเท่าเดิม ชีตมีเพดานจำนวนแถว พอเต็มแล้วการรวมยอด
จะเขียนแถวใหม่ไม่ได้ ตอบ 400 exceeds grid limits แล้วทิ้งทั้ง batch ผลคือ กก. ที่
ยังไม่มีแถวของวันนั้นหายไปจากหน้า ผบก. เงียบ ๆ

    python scripts/purge_summary_rows.py            # ดูว่าจะลบอะไร ไม่เขียนอะไร
    python scripts/purge_summary_rows.py --apply    # ลบจริง
    python scripts/purge_summary_rows.py --apply --shrink   # ลบแล้วหดขนาดชีตด้วย

ลบแล้วกู้จากในระบบไม่ได้ ก่อนรัน --apply ควรก๊อปชีตเก็บไว้สักชุด
(ใน Google Sheets: คลิกขวาที่แท็บ > ทำสำเนา)

ตัวสคริปต์ตรวจให้เองว่าแถวที่ยัง Active ครบเท่าเดิมหลังลบ ถ้าหายแม้แถวเดียวจะแจ้ง
ว่าผิดปกติ แต่ย้อนกลับให้ไม่ได้ — นั่นคือเหตุผลที่ต้องมีสำเนา
"""

import argparse
import os
import sys
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import MASTER_SHEET_ID  # noqa: E402
from app.services import query_service, sheets_service  # noqa: E402
from app.services.national_service import SUMMARY_TABLE  # noqa: E402

COL_IS_ACTIVE = query_service.COL_IS_ACTIVE
COL_DATE = query_service.COL_ACTUAL_DATE
COL_STATION = query_service.COL_STATION_ID

# เผื่อพื้นที่ว่างไว้เท่านี้ตอน --shrink จะได้ไม่ต้องขยายชีตในรอบรวมยอดถัดไปทันที
HEADROOM_ROWS = 300


def active_key_set(rows: List[Dict[str, Any]]) -> set:
    return {
        (str(r.get(COL_DATE, "")), str(r.get(COL_STATION, "")), r["_row"])
        for r in rows
        if query_service.is_active(r.get(COL_IS_ACTIVE))
    }


def contiguous_ranges(numbers: List[int]) -> List[Tuple[int, int]]:
    """
    รวมเลขแถวที่ติดกันเป็นช่วง เพื่อลบทีละช่วงแทนทีละแถว

    814 แถวถ้าลบทีละแถวคือ 814 คำขอ ชนโควตาเขียนของ Google แน่นอน
    """
    if not numbers:
        return []
    ordered = sorted(numbers)
    ranges = [(ordered[0], ordered[0])]
    for n in ordered[1:]:
        start, end = ranges[-1]
        if n == end + 1:
            ranges[-1] = (start, n)
        else:
            ranges.append((n, n))
    return ranges


def main() -> int:
    parser = argparse.ArgumentParser(description="ลบแถวที่ถูกปิดออกจากตารางสรุประดับประเทศ")
    parser.add_argument("--apply", action="store_true", help="ลบจริง")
    parser.add_argument("--shrink", action="store_true", help="หดขนาดชีตหลังลบ (ใช้ร่วมกับ --apply)")
    args = parser.parse_args()

    if not sheets_service.is_configured():
        print(sheets_service.NOT_CONFIGURED_MESSAGE)
        return 1

    worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, SUMMARY_TABLE, ensure=False)
    rows = query_service.read_rows(MASTER_SHEET_ID, SUMMARY_TABLE)

    dead = [r["_row"] for r in rows if not query_service.is_active(r.get(COL_IS_ACTIVE))]
    alive_before = active_key_set(rows)

    print(f"ขนาดชีต        {worksheet.row_count} แถว")
    print(f"แถวข้อมูล       {len(rows)}")
    print(f"ยัง Active      {len(alive_before)}")
    print(f"ปิดแล้ว (จะลบ)  {len(dead)}")

    if not dead:
        print("\nไม่มีแถวที่ต้องลบ")
        return 0

    ranges = contiguous_ranges(dead)
    print(f"รวมเป็น {len(ranges)} ช่วงติดกัน")

    if not args.apply:
        print("\nโหมดแสดงผลอย่างเดียว — ใส่ --apply เพื่อลบจริง")
        print("แนะนำให้ทำสำเนาแท็บเก็บไว้ก่อน ลบแล้วกู้ไม่ได้")
        return 0

    # ลบจากล่างขึ้นบน ไม่งั้นเลขแถวที่เหลือจะเลื่อนขึ้นหลังลบช่วงแรกไปแล้ว
    for start, end in sorted(ranges, reverse=True):
        sheets_service.with_backoff(worksheet.delete_rows, start, end)
    print(f"\nลบไปแล้ว {len(dead)} แถว")

    after = query_service.read_rows(MASTER_SHEET_ID, SUMMARY_TABLE)
    alive_after = active_key_set(after)

    # เลขแถวเลื่อนหลังลบ จึงเทียบเฉพาะ (วันที่, กก.) ไม่เอาเลขแถวมาเทียบ
    keys_before = {(d, s) for d, s, _ in alive_before}
    keys_after = {(d, s) for d, s, _ in alive_after}
    missing = keys_before - keys_after

    if missing:
        print(f"ผิดปกติ: แถวที่ยังใช้งานหายไป {len(missing)} รายการ")
        for key in sorted(missing)[:10]:
            print(f"  วันที่ {key[0]} กก.{key[1]}")
        print("กู้คืนจากสำเนาที่ทำไว้ แล้วแจ้งผู้ดูแลระบบ")
        return 1

    print(f"ตรวจแล้ว: แถวที่ใช้งานครบ {len(keys_after)} รายการเท่าเดิม")

    if args.shrink:
        target = len(after) + 1 + HEADROOM_ROWS
        if target < worksheet.row_count:
            sheets_service.with_backoff(worksheet.resize, rows=target)
            print(f"หดขนาดชีตเหลือ {target} แถว (เผื่อว่างไว้ {HEADROOM_ROWS})")
        else:
            print("ขนาดชีตเล็กพออยู่แล้ว ไม่ต้องหด")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
