"""
อัปเดตหัวคอลัมน์ของแท็บที่มีอยู่แล้ว ให้ตรงกับ `schema.py` ปัจจุบัน

`ensure_worksheet` เขียนหัวคอลัมน์ให้เฉพาะแท็บที่สร้างใหม่หรือแถวแรกยังว่าง แท็บเดิม
ที่ใช้งานอยู่จึงยังถือหัวตารางชุดเก่า พอ schema เพิ่มคอลัมน์ ข้อมูลจะลงในช่องที่ไม่มี
ป้ายกำกับ โค้ดอ่านถูกเพราะอ้างด้วยตำแหน่ง แต่คนที่เปิดชีตดูจะไม่รู้ว่าช่องนั้นคืออะไร

สคริปต์นี้แตะเฉพาะ **แถวที่ 1** ไม่แตะข้อมูล และปฏิเสธที่จะทำงานถ้าหัวตารางเดิม
ยาวกว่า schema ซึ่งแปลว่ามีคนเพิ่มคอลัมน์ในชีตเองโดยที่โค้ดไม่รู้ ต้องมีคนดูก่อน

ตัวอย่าง:
    cd python_backend

    # ดูก่อนว่าจะแก้แท็บไหนบ้าง โดยยังไม่เขียนจริง
    python scripts/sync_sheet_headers.py --dry-run

    # เขียนจริงเฉพาะ กก.5
    python scripts/sync_sheet_headers.py --divisions 5
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import MASTER_SHEET_ID, get_db_router  # noqa: E402
from app.core.schema import TABLE_COLUMNS, get_columns  # noqa: E402
from app.services import sheets_service  # noqa: E402

# ตารางที่อยู่ในสเปรดชีตกลาง ไม่ใช่ของ กก. — tb_Users ไม่แตะเพราะแถวท้ายตารางเก็บ
# รายการ Role ไว้เป็นแหล่งข้อมูล dropdown ไม่ใช่หัวคอลัมน์ล้วน ๆ
MASTER_TABLES = ("tb_National_Summary", "tb_Charges", "tb_ReportCatalog")
SKIP_TABLES = ("tb_Users",)

# หลักฐานประกอบการใช้ --force-tables เมื่อ 5 ส.ค. 2569
#
# ชีตของ กก.1 ถือชื่อหัวคอลัมน์รุ่นเก่าไว้สี่แท็บ สคริปต์จึงตีเป็น conflict และข้ามให้
# ก่อนตัดสินใจเขียนทับ ได้ดึงค่าจริงในคอลัมน์นั้นมาดูทีละช่อง ผลคือ **ข้อมูลตรงกับ
# ความหมายของ schema อยู่แล้วทุกจุด ผิดแค่ป้ายชื่อหัว** ไม่มีคอลัมน์ไหนเลื่อน
#
#   tb_DailyReport ช่อง 14  ป้าย "รถวิทยุตรวจเขต" แต่ข้อมูลจริงคือ "พ.ต.ท.พิชญา ทวิชศรี สว."
#                           ซึ่งเป็นชื่อและยศ ตรงกับ schema "พลขับ (ชื่อและยศ)"
#   tb_Arrests     ช่อง 27  ป้าย "Structured_Items" แต่ข้อมูลจริงคือ "ไม่ใช่หมายจับ"
#                           ซึ่งเป็นขอบเขตหมาย ตรงกับ schema "ขอบเขตหมาย"
#   tb_StationDuty ช่อง 12/14/16  ป้าย "เบอร์โทร" เหมือนกันหมด ข้อมูลจริงเป็นเบอร์โทร
#                           schema แค่ระบุให้ชัดว่าเป็นเบอร์ของใคร
#   tb_HQ_Escorts  ช่อง 11/12/14  ตารางยังไม่มีข้อมูลสักแถว ไม่มีอะไรให้เสีย
#
# การเขียนทับจึงแก้ป้ายที่ผิดให้ถูกด้วยซ้ำ — ช่อง 14 ของ tb_DailyReport เขียนว่า
# "รถวิทยุตรวจเขต" แต่เก็บชื่อพลขับ ใครเปิดชีตดูตรง ๆ จะเข้าใจผิดทันที
#
# **ห้ามใช้ flag นี้กับแท็บที่ยังไม่ได้ตรวจข้อมูลจริง** ถ้าคอลัมน์เลื่อนจริง การเขียนหัว
# ทับจะทำให้ข้อมูลเก่าถูกตีความผิดถาวรโดยไม่มีอะไรฟ้อง


def plan_for_worksheet(spreadsheet, table_name):
    """
    คืน (สถานะ, หัวเดิม, หัวใหม่) ของแท็บหนึ่ง โดยไม่เขียนอะไรทั้งสิ้น

    สถานะ: ok = ตรงอยู่แล้ว, update = ต้องเขียนทับ, missing = ยังไม่มีแท็บ,
           conflict = หัวเดิมยาวกว่า schema หรือชนกัน ต้องให้คนตัดสิน
    """
    import gspread

    try:
        columns = get_columns(table_name)
    except KeyError:
        return "skip", [], []

    try:
        worksheet = sheets_service.with_backoff(spreadsheet.worksheet, table_name)
    except gspread.exceptions.WorksheetNotFound:
        return "missing", [], columns

    current = sheets_service.with_backoff(worksheet.row_values, 1)

    if current == columns:
        return "ok", current, columns
    if len(current) > len(columns):
        return "conflict", current, columns
    # หัวเดิมต้องเป็นคำนำหน้าของหัวใหม่ ไม่งั้นแปลว่าคอลัมน์ถูกแทรกกลางตาราง
    # ซึ่งย้ายข้อมูลผิดช่องทั้งตาราง ห้ามแก้อัตโนมัติเด็ดขาด
    if current and current != columns[: len(current)]:
        return "conflict", current, columns

    return "update", current, columns


def sync_spreadsheet(spreadsheet_id, tables, label, dry_run, force_tables=()):
    """อัปเดตหัวคอลัมน์ทุกแท็บในสเปรดชีตเดียว คืนจำนวนที่แก้กับจำนวนที่ติดปัญหา"""
    spreadsheet = sheets_service.open_spreadsheet(spreadsheet_id)
    updated = conflicts = 0

    for table_name in tables:
        status, current, columns = plan_for_worksheet(spreadsheet, table_name)

        if status in ("ok", "skip"):
            continue
        if status == "missing":
            print(f"  - {table_name}: ยังไม่มีแท็บนี้ ข้ามไป (จะถูกสร้างเองตอนมีคนบันทึกครั้งแรก)")
            continue
        if status == "conflict" and table_name not in force_tables:
            conflicts += 1
            print(f"  ! {table_name}: หัวตารางในชีตไม่ตรงกับ schema แบบที่แก้อัตโนมัติไม่ได้")
            print(f"      ในชีต ({len(current)} ช่อง): {current}")
            print(f"      schema ({len(columns)} ช่อง): {columns}")
            continue

        if status == "conflict":
            # เขียนทับทั้งที่ชื่อหัวไม่ตรง — ทำได้เฉพาะเมื่อ **ตรวจข้อมูลจริงในคอลัมน์นั้นแล้ว**
            # ว่าตรงกับความหมายของ schema ดูเหตุผลรายคอลัมน์ที่ FORCE_EVIDENCE ข้างบน
            renamed = [
                f"ช่อง {i + 1}: \"{current[i]}\" -> \"{columns[i]}\""
                for i in range(min(len(current), len(columns)))
                if current[i] != columns[i]
            ]
            print(f"  * {table_name}: เขียนทับชื่อหัวที่ไม่ตรง {len(renamed)} ช่อง")
            for line in renamed:
                print(f"      {line}")
        else:
            added = columns[len(current):]
            print(f"  + {table_name}: เพิ่มหัวคอลัมน์ {len(added)} ช่อง -> {added}")
        updated += 1

        if not dry_run:
            worksheet = sheets_service.with_backoff(spreadsheet.worksheet, table_name)
            # ขยายจำนวนคอลัมน์ก่อน ไม่งั้น update จะตกขอบตาราง
            if worksheet.col_count < len(columns):
                sheets_service.with_backoff(worksheet.add_cols, len(columns) - worksheet.col_count)
            sheets_service.with_backoff(worksheet.update, range_name="A1", values=[columns])
            sheets_service.with_backoff(worksheet.freeze, rows=1)

    print(f"  สรุป {label}: แก้ {updated} แท็บ ติดปัญหา {conflicts} แท็บ")
    return updated, conflicts


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--divisions", default="", help="เลข กก. คั่นด้วยลูกน้ำ เว้นว่าง = ทุก กก. ที่ตั้งค่าไว้")
    parser.add_argument("--dry-run", action="store_true", help="แสดงสิ่งที่จะทำโดยไม่เขียนจริง")
    parser.add_argument("--skip-master", action="store_true", help="ไม่ต้องแตะสเปรดชีตกลาง")
    parser.add_argument(
        "--force-tables",
        default="",
        help="ชื่อแท็บคั่นด้วยลูกน้ำ ที่ยอมให้เขียนหัวทับแม้ชื่อไม่ตรง "
             "ใช้ได้ต่อเมื่อตรวจข้อมูลจริงในคอลัมน์นั้นแล้ว (ดูหมายเหตุ FORCE ในไฟล์นี้)",
    )
    args = parser.parse_args()

    if args.dry_run:
        print("โหมดดูอย่างเดียว ยังไม่เขียนอะไรลงชีต\n")

    router = get_db_router()
    wanted = [d.strip() for d in args.divisions.split(",") if d.strip()] or sorted(router)

    division_tables = [t for t in TABLE_COLUMNS if t not in MASTER_TABLES and t not in SKIP_TABLES]
    force = tuple(t.strip() for t in args.force_tables.split(",") if t.strip())
    if force:
        print(f"โหมดเขียนทับหัวที่ไม่ตรง: {', '.join(force)}\n")
    total_updated = total_conflicts = 0

    for division in wanted:
        sheet_id = (router.get(division) or {}).get("OPS", "")
        if not sheet_id:
            print(f"กก.{division}: ยังไม่ได้ตั้งค่า DB_ROUTER ข้ามไป")
            continue
        print(f"กก.{division} ({sheet_id})")
        updated, conflicts = sync_spreadsheet(sheet_id, division_tables, f"กก.{division}", args.dry_run, force)
        total_updated += updated
        total_conflicts += conflicts

    if not args.skip_master:
        print(f"\nสเปรดชีตกลาง ({MASTER_SHEET_ID})")
        updated, conflicts = sync_spreadsheet(MASTER_SHEET_ID, MASTER_TABLES, "ส่วนกลาง", args.dry_run, force)
        total_updated += updated
        total_conflicts += conflicts

    print(f"\nรวมทั้งหมด: แก้ {total_updated} แท็บ ติดปัญหา {total_conflicts} แท็บ")
    return 1 if total_conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
