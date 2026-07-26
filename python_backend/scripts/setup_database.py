"""
สร้างฐานข้อมูล (Google Spreadsheet + แท็บ) สำหรับ กก. ที่ระบุ ลงในโฟลเดอร์ Drive ที่กำหนด

รันซ้ำได้ปลอดภัย ถ้ามีสเปรดชีตชื่อเดิมอยู่แล้วจะใช้ไฟล์เดิมและเติมเฉพาะแท็บที่ยังขาด

ตัวอย่าง:
    cd python_backend
    export GOOGLE_SERVICE_ACCOUNT_JSON=./service-account.json

    # ดูก่อนว่าจะทำอะไรบ้าง โดยยังไม่แตะของจริง
    python scripts/setup_database.py --divisions 5 --dry-run

    # สร้างจริง แล้วแชร์กลับให้เจ้าของบัญชีแก้ไขได้
    python scripts/setup_database.py --divisions 5 --share-with you@gmail.com

เมื่อเสร็จ สคริปต์จะพิมพ์ค่า DB_ROUTER_JSON ให้เอาไปใส่ .env หรือ Render ได้ทันที
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.schema import TABLE_COLUMNS  # noqa: E402
from app.services import sheets_service  # noqa: E402

# โฟลเดอร์ "ตัวเทส ระดับ บก." ที่ใช้เป็นฐานข้อมูลชั่วคราวระหว่างทดสอบ
DEFAULT_FOLDER_ID = "1K-Aag2OZ13UmvWbBmaG8RC78huY7pDCb"

# ตั้งชื่อตามที่ใช้อยู่จริงในโฟลเดอร์ (DB_TEST_กก.1) ไม่ใช่ชื่อแบบใหม่ที่ไม่เข้าพวก
DEFAULT_TITLE_PATTERN = "DB_TEST_กก.{division}"
# โฟลเดอร์เก็บไฟล์แนบ ใช้ชื่อเดิมที่มีอยู่แล้วในโฟลเดอร์ (กองกำกับ 1, กองกำกับ 2)
DEFAULT_FOLDER_PATTERN = "กองกำกับ {division}"


def find_child_folder(service, parent_id: str, name: str):
    """หาโฟลเดอร์ย่อยตามชื่อ เพื่อให้รันซ้ำแล้วไม่สร้างซ้ำ"""
    escaped = name.replace("'", "\\'")
    query = (
        f"'{parent_id}' in parents and name = '{escaped}' "
        "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    found = service.files().list(q=query, fields="files(id,name)", pageSize=5).execute().get("files", [])
    return found[0] if found else None


def setup_attachment_folder(service, division: str, parent_id: str, pattern: str, dry_run: bool):
    """สร้าง (หรือใช้ของเดิม) โฟลเดอร์เก็บไฟล์แนบของ กก. นั้น"""
    name = pattern.format(division=division)
    existing = find_child_folder(service, parent_id, name)

    if existing:
        print(f"    โฟลเดอร์ไฟล์แนบ: ใช้ของเดิม {name} ({existing['id']})")
        return existing["id"]

    if dry_run:
        print(f"    โฟลเดอร์ไฟล์แนบ: [dry-run] จะสร้าง {name}")
        return None

    created = service.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]},
        fields="id",
    ).execute()
    print(f"    โฟลเดอร์ไฟล์แนบ: สร้างแล้ว {name} ({created['id']})")
    return created["id"]


def extract_drive_id(value: str) -> str:
    """รับได้ทั้งลิงก์เต็มและ ID เปล่า ๆ"""
    match = re.search(r"/(?:folders|d)/([A-Za-z0-9_-]{20,})", value or "")
    return match.group(1) if match else (value or "").strip()


def find_existing(client, title: str, folder_id: str):
    """หาไฟล์ชื่อเดียวกันในโฟลเดอร์ เพื่อให้รันซ้ำแล้วไม่สร้างซ้ำ"""
    for item in client.list_spreadsheet_files(folder_id=folder_id):
        if item.get("name") == title:
            return client.open_by_key(item["id"])
    return None


def setup_division(client, division, folder_id, title_pattern, dry_run, share_with, spreadsheet_id=""):
    title = title_pattern.format(division=division)

    if spreadsheet_id:
        spreadsheet = client.open_by_key(spreadsheet_id)
        print(f"  ใช้สเปรดชีตที่ระบุ: {spreadsheet.title} ({spreadsheet.id})")
    else:
        spreadsheet = find_existing(client, title, folder_id)

        if spreadsheet is None:
            if dry_run:
                print(f"  [dry-run] จะสร้างสเปรดชีตใหม่ชื่อ {title}")
                return None
            spreadsheet = client.create(title, folder_id=folder_id)
            print(f"  สร้างสเปรดชีตใหม่: {title} ({spreadsheet.id})")
        else:
            print(f"  ใช้สเปรดชีตเดิม: {title} ({spreadsheet.id})")

    existing_tabs = [ws.title for ws in spreadsheet.worksheets()]

    for table_name in sorted(TABLE_COLUMNS):
        if table_name in existing_tabs:
            print(f"    - {table_name}: มีอยู่แล้ว ข้าม")
            continue
        if dry_run:
            print(f"    - {table_name}: [dry-run] จะสร้างพร้อมหัวคอลัมน์ {len(TABLE_COLUMNS[table_name])} ช่อง")
            continue
        sheets_service.ensure_worksheet(spreadsheet, table_name)
        print(f"    - {table_name}: สร้างแล้ว ({len(TABLE_COLUMNS[table_name])} คอลัมน์)")

    # Google สร้างแท็บเปล่าชื่อ Sheet1 มาให้เสมอ ลบทิ้งเมื่อมีตารางจริงแล้ว
    if not dry_run:
        for ws in spreadsheet.worksheets():
            if ws.title in ("Sheet1", "แผ่น1") and len(spreadsheet.worksheets()) > 1:
                spreadsheet.del_worksheet(ws)
                print("    - ลบแท็บเปล่าที่ Google สร้างมาให้")
                break

        if share_with:
            spreadsheet.share(share_with, perm_type="user", role="writer", notify=False)
            print(f"    - แชร์ให้ {share_with} (writer)")

    return spreadsheet.id


def main() -> int:
    parser = argparse.ArgumentParser(description="สร้างฐานข้อมูล Google Sheets ของแต่ละ กก.")
    parser.add_argument("--folder-id", default=DEFAULT_FOLDER_ID, help="ID หรือลิงก์โฟลเดอร์ Drive ปลายทาง")
    parser.add_argument("--divisions", default="5", help="หมายเลข กก. คั่นด้วยจุลภาค เช่น 1,5")
    parser.add_argument(
        "--title-pattern",
        default=DEFAULT_TITLE_PATTERN,
        help=f"รูปแบบชื่อไฟล์ ใช้ {{division}} แทนหมายเลข กก. (ค่าเริ่มต้น: {DEFAULT_TITLE_PATTERN})",
    )
    parser.add_argument(
        "--spreadsheet-id",
        default="",
        help="ใช้สเปรดชีตที่มีอยู่แล้วแทนการสร้างใหม่ (ระบุได้เมื่อทำทีละ กก. เท่านั้น)",
    )
    parser.add_argument(
        "--folder-pattern",
        default=DEFAULT_FOLDER_PATTERN,
        help=f"รูปแบบชื่อโฟลเดอร์ไฟล์แนบ (ค่าเริ่มต้น: {DEFAULT_FOLDER_PATTERN})",
    )
    parser.add_argument("--skip-folders", action="store_true", help="ข้ามการสร้างโฟลเดอร์ไฟล์แนบ")
    parser.add_argument("--share-with", default="", help="อีเมลที่จะแชร์สิทธิ์แก้ไขให้หลังสร้างเสร็จ")
    parser.add_argument("--dry-run", action="store_true", help="แสดงสิ่งที่จะทำโดยไม่แก้ไขอะไรจริง")
    args = parser.parse_args()

    if not sheets_service.is_configured():
        print(sheets_service.NOT_CONFIGURED_MESSAGE, file=sys.stderr)
        return 1

    folder_id = extract_drive_id(args.folder_id)
    divisions = [d.strip() for d in args.divisions.split(",") if d.strip()]

    if args.spreadsheet_id and len(divisions) != 1:
        print("--spreadsheet-id ใช้ได้ทีละ กก. เท่านั้น", file=sys.stderr)
        return 1

    email = sheets_service.service_account_email()
    mode = sheets_service.auth_mode()
    print(f"โหมดเข้าถึง Google: {mode}" + (f" ({email})" if email else " (ในนามบัญชีที่ให้ consent)"))
    print(f"โฟลเดอร์ปลายทาง: {folder_id}")
    print()

    try:
        client = sheets_service.get_client()
    except sheets_service.SheetNotConfigured as exc:
        print(str(exc), file=sys.stderr)
        return 1

    drive = None
    if not args.skip_folders:
        from app.services.storage_service import drive_service

        drive = drive_service()

    router = {}
    folders = {}
    for division in divisions:
        print(f"กองกำกับการ {division}:")
        try:
            sheet_id = setup_division(
                client,
                division,
                folder_id,
                args.title_pattern,
                args.dry_run,
                args.share_with,
                extract_drive_id(args.spreadsheet_id) if args.spreadsheet_id else "",
            )
            attachment_folder = None
            if drive is not None:
                attachment_folder = setup_attachment_folder(
                    drive, division, folder_id, args.folder_pattern, args.dry_run
                )
        except Exception as exc:  # noqa: BLE001 - แสดงสาเหตุจริงให้ผู้ใช้เห็น
            print(f"  ล้มเหลว: {exc}", file=sys.stderr)
            print(f"  ตรวจว่าโฟลเดอร์ถูกแชร์ให้ {email} ในสิทธิ์ Editor แล้วหรือยัง", file=sys.stderr)
            return 1
        if sheet_id:
            router[division] = {"OPS": sheet_id}
        if attachment_folder:
            folders[division] = attachment_folder
        print()

    if router:
        print("เอาค่านี้ไปใส่ .env หรือ Environment ของ Render:")
        print()
        print(f"DB_ROUTER_JSON={json.dumps(router, ensure_ascii=False, separators=(',', ':'))}")
    if folders:
        print(f"DIVISION_FOLDERS_JSON={json.dumps(folders, ensure_ascii=False, separators=(',', ':'))}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
