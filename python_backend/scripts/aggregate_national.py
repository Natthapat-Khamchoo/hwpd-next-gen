"""
รวมยอดของทุก กก. ลงแท็บ `tb_National_Summary` ในชีตกลาง

หน้า dashboard ระดับประเทศอ่านจากตารางนี้ตารางเดียว ถ้าไม่รันสคริปต์นี้ หน้านั้น
จะแสดงข้อมูลเก่าค้างอยู่ ไม่ใช่ error — ให้รันตามรอบด้วย cron

    python scripts/aggregate_national.py                    # ย้อนหลัง 7 วันถึงวันนี้
    python scripts/aggregate_national.py --days 30
    python scripts/aggregate_national.py --start 2026-07-01 --end 2026-07-31
    python scripts/aggregate_national.py --divisions 1 5    # เฉพาะบาง กก.
    python scripts/aggregate_national.py --dry-run          # ดูยอดโดยไม่เขียน

แถวของ (วันที่, กก.) ที่มีอยู่แล้วจะถูกเขียนทับที่เดิม ไม่ต่อท้ายใหม่ จึงรันซ้ำได้
โดยตารางไม่บวม และยอดไม่ถูกนับซ้ำ
"""

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import national_service, sheets_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="รวมยอดระดับประเทศลง tb_National_Summary")
    parser.add_argument("--start", default="", help="วันที่เริ่ม (YYYY-MM-DD)")
    parser.add_argument("--end", default="", help="วันที่สิ้นสุด (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=7, help="ย้อนหลังกี่วันเมื่อไม่ระบุ --start/--end")
    parser.add_argument("--divisions", nargs="*", default=None, help="เลข กก. ที่ต้องการ (เว้นว่าง = ทุก กก. ที่ตั้งค่าแล้ว)")
    parser.add_argument("--dry-run", action="store_true", help="คำนวณและแสดงผล แต่ไม่เขียนลงชีต")
    parser.add_argument("--dedupe", action="store_true", help="ปิดแถวซ้ำในตารางสรุปแล้วจบ ไม่รวมยอดใหม่")
    parser.add_argument("--verbose", action="store_true", help="แสดงบันทึกระหว่างทำงาน")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    start, end = (args.start, args.end)
    if not (start and end):
        start, end = national_service.default_range(args.days)
    print(f"ช่วงวันที่ {start} ถึง {end}")

    if not sheets_service.is_configured():
        print(sheets_service.NOT_CONFIGURED_MESSAGE)
        return 1

    if args.dedupe:
        result = national_service.deactivate_duplicates()
        print(f"คู่ (วันที่, กก.) ที่เหลืออยู่ {result['keys']} คู่ ปิดแถวซ้ำไป {result['deactivated']} แถว")
        return 0

    divisions = args.divisions or national_service._configured_divisions()
    if not divisions:
        print("ยังไม่มี กก. ไหนตั้งค่าฐานข้อมูลไว้ (DB_ROUTER_JSON)")
        return 1
    print(f"กองกำกับการ: {', '.join(divisions)}\n")

    if args.dry_run:
        grand = 0
        for division in divisions:
            days = national_service.aggregate_division(division, start, end)
            arrests = sum(v["arrestsCount"] for v in days.values())
            v20 = sum(v["v20Count"] for v in days.values())
            accidents = sum(v["accCount"] for v in days.values())
            grand += len(days)
            print(f"  กก.{division}: {len(days)} วัน | จับกุม {arrests} | ว.20 {v20} | อุบัติเหตุ {accidents}")
        print(f"\nรวม {grand} แถวที่จะเขียน (โหมดแสดงผลอย่างเดียว ยังไม่ได้เขียนลงชีต)")
        return 0

    try:
        result = national_service.aggregate_national(start, end, divisions)
    except (sheets_service.SheetNotConfigured, sheets_service.SheetWriteError) as exc:
        print(f"รวมยอดไม่สำเร็จ: {exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(
        f"\nเสร็จแล้ว: เขียนทับ {result['replaced']} แถว "
        f"เพิ่มใหม่ {result['appended']} แถว ปิดแถวซ้ำ {result['deactivated']} แถว"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
