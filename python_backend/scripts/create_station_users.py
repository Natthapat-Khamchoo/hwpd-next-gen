"""
สร้างและดูแลบัญชีผู้ใช้ประจำสถานีและประจำกองกำกับการในแท็บ `tb_Users` ของชีตกลาง

โครงสร้างบัญชี (1 บัญชีต่อ 1 หน่วย) อ่านรายชื่อสถานีจาก STATION_CONFIG โดยตรง

    00       บก.ทล. ส่วนกลาง   Super_Commander   username: hq
    {d}0     ฝอ.กก.{d}         Division_Admin    username: fo{d}
    {d}{n}   ส.ทล.{n} กก.{d}   Station_Admin     username: st{d}{n}

รหัสผ่านสุ่มไม่ซ้ำกันต่อบัญชี เก็บลงชีตเป็น `sha256$...` (ดู core/security.py)
ส่วนรหัสตัวจริงเขียนลงไฟล์ CSV บนเครื่องเท่านั้น เพื่อแจกให้แต่ละหน่วย

    python scripts/create_station_users.py            # ดูว่าจะทำอะไรบ้าง ไม่เขียนอะไร
    python scripts/create_station_users.py --apply    # สร้างบัญชีที่ยังขาด
    python scripts/create_station_users.py --sync     # อัปเดตชื่อหน่วย/สถานีของบัญชีเดิม
    python scripts/create_station_users.py --prune    # ลบบัญชีของสถานีที่ไม่มีใน STATION_CONFIG

ทั้งสามโหมดใช้ร่วมกันได้และรันซ้ำได้ `--prune` แตะเฉพาะบัญชีที่ตั้งชื่อตามรูปแบบ
ของสคริปต์นี้ (hq / fo{d} / st{dn}) จึงไม่ไปโดนบัญชีที่คนอื่นสร้างไว้
"""

import argparse
import csv
import os
import re
import secrets
import sys
from datetime import datetime
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import (  # noqa: E402
    MASTER_SHEET_ID,
    get_division_stations,
    get_station_config,
    get_station_data,
)
from app.core.security import hash_password  # noqa: E402
from app.services import sheets_service, user_service  # noqa: E402

USERS_TABLE = "tb_Users"
DIVISIONS = range(1, 9)

# ชื่อบัญชีที่สคริปต์นี้เป็นเจ้าของ ใช้กันไม่ให้ --prune ไปลบบัญชีของคนอื่น
OWNED_USERNAME = re.compile(r"^(hq|fo[1-8]|st[1-8][1-9])$")

# ตัดตัวที่อ่านสับสนออก (0/O, 1/l/I) เพราะรหัสนี้ต้องอ่านจากกระดาษแล้วพิมพ์ตาม
PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789abcdefghijkmnpqrstuvwxyz"
PASSWORD_LENGTH = 8

# ลำดับคอลัมน์ A-N ของ tb_Users
# AccountType (คอลัมน์ N) เพิ่มขึ้นมาทีหลัง แยกบัญชีประจำหน่วยออกจากบัญชีเจ้าหน้าที่
# ต่อท้ายตารางเท่านั้น เพราะ Apps Script อ่านคอลัมน์ A-M ด้วยตำแหน่ง
COLUMNS = [
    "Username",
    "Password",
    "FullName",
    "Station_ID",
    "Unit_ID",
    "Role",
    "สถานะไปช่วยราชการ",
    "สถานะมาช่วยราชการ",
    "หมายเหตุ",
    "เบอร์โทร",
    "รหัส",
    "วันที่เริ่มช่วยราชการ",
    "วันที่สิ้นสุดช่วยราชการ",
    "AccountType",
]

ACCOUNT_TYPE_COLUMN = "AccountType"
LAST_COLUMN = chr(ord("A") + len(COLUMNS) - 1)


def generate_password() -> str:
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))


def build_accounts() -> List[Dict[str, Any]]:
    """
    ประกอบรายการบัญชีจากสถานีที่มีจริงใน STATION_CONFIG

    จำนวนสถานีไม่เท่ากันทุก กก. (กก.3, 4, 7 มี 5 สถานี กก.8 มี 4) จึงต้องอ่าน
    จาก config ไม่ใช่สมมติว่า กก.ละ 6 สถานี
    """
    config = get_station_config()
    accounts: List[Dict[str, Any]] = []

    def add(station_id: str, username: str, role: str) -> None:
        data = get_station_data(station_id)
        units = data.get("units") or []
        accounts.append(
            {
                "username": username,
                "password": generate_password(),
                "fullName": data.get("fullName", ""),
                "station": station_id,
                "unit": units[0] if units else "",
                "role": role,
                "province": data.get("province", ""),
                "unitCount": len(units),
            }
        )

    if "00" in config:
        add("00", "hq", "Super_Commander")

    for division in DIVISIONS:
        hq_id = f"{division}0"
        if hq_id in config:
            add(hq_id, f"fo{division}", "Division_Admin")
        for station_id in get_division_stations(hq_id, include_hq=False):
            add(station_id, f"st{station_id}", "Station_Admin")

    return accounts


def read_sheet_users(rows: List[List[str]]) -> Dict[str, Tuple[int, Dict[str, str]]]:
    """คืน username (ตัวพิมพ์เล็ก) -> (เลขแถวในชีต, ค่าแต่ละคอลัมน์)"""
    if not rows:
        return {}
    header = [str(h).strip() for h in rows[0]]
    if "Username" not in header:
        raise SystemExit(f"ตาราง {USERS_TABLE} ไม่มีคอลัมน์ Username")

    positions = {column: header.index(column) for column in COLUMNS if column in header}
    found: Dict[str, Tuple[int, Dict[str, str]]] = {}

    for line, row in enumerate(rows[1:], start=2):
        def cell(column: str) -> str:
            index = positions.get(column)
            return str(row[index]).strip() if index is not None and index < len(row) else ""

        name = cell("Username")
        if name:
            found[name.lower()] = (line, {column: cell(column) for column in positions})
    return found


def first_free_row(rows: List[List[str]]) -> int:
    """
    แถวว่างแถวแรกที่นับจากคอลัมน์ Username เท่านั้น

    ชีตจริงมีรายการ Role ห้อยอยู่ในคอลัมน์ท้าย ๆ (แหล่งข้อมูลของ dropdown)
    ถ้าใช้ append_row ตามปกติ Google จะข้ามไปต่อท้ายรายการนั้นแล้วเว้นแถวว่าง
    กลางตารางทิ้งไว้ จึงต้องหาตำแหน่งจากคอลัมน์ A เอง
    """
    last = 1
    for line, row in enumerate(rows[1:], start=2):
        if row and str(row[0]).strip():
            last = line
    return last + 1


def to_sheet_row(account: Dict[str, Any], plaintext: bool) -> List[str]:
    stored = (
        account["password"]
        if plaintext
        else hash_password(account["username"], account["password"])
    )
    return [
        account["username"],
        stored,
        account["fullName"],
        account["station"],
        account["unit"],
        account["role"],
        "",  # สถานะไปช่วยราชการ
        "",  # สถานะมาช่วยราชการ
        "",  # หมายเหตุ
        "",  # เบอร์โทร
        "",  # รหัส
        "",  # วันที่เริ่มช่วยราชการ
        "",  # วันที่สิ้นสุดช่วยราชการ
        user_service.UNIT_ACCOUNT_TYPE,
    ]


def ensure_account_type_header(rows: List[List[str]]) -> bool:
    """
    เขียนหัวคอลัมน์ AccountType ถ้ายังไม่มี คืน True เมื่อเพิ่งเพิ่ม

    ต่อท้ายตำแหน่งที่ 14 (คอลัมน์ N) ซึ่งว่างอยู่ ไม่แทรกกลางตาราง เพราะ Apps Script
    อ้างอิงคอลัมน์ A-M ด้วยตำแหน่ง การแทรกจะทำให้ทุกฟังก์ชันฝั่งนั้นอ่านผิดช่องทันที
    """
    header = [str(h).strip() for h in (rows[0] if rows else [])]
    if ACCOUNT_TYPE_COLUMN in header:
        return False

    worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, USERS_TABLE, ensure=False)
    sheets_service.with_backoff(
        worksheet.update,
        range_name=f"{LAST_COLUMN}1",
        values=[[ACCOUNT_TYPE_COLUMN]],
        value_input_option="RAW",
    )
    return True


def write_credentials_file(accounts: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Username", "Password", "Station_ID", "หน่วย", "จังหวัด", "Role", "จำนวนหน่วยบริการ"])
        for account in accounts:
            writer.writerow(
                [
                    account["username"],
                    account["password"],
                    account["station"],
                    account["fullName"],
                    account["province"],
                    account["role"],
                    account["unitCount"],
                ]
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="สร้างและดูแลบัญชีประจำสถานีและกองกำกับการใน tb_Users")
    parser.add_argument("--apply", action="store_true", help="สร้างบัญชีที่ยังไม่มีในชีต")
    parser.add_argument("--sync", action="store_true", help="อัปเดต FullName/Unit_ID/Role ของบัญชีเดิมให้ตรง STATION_CONFIG")
    parser.add_argument("--prune", action="store_true", help="ลบบัญชีของสถานีที่ไม่มีใน STATION_CONFIG แล้ว")
    parser.add_argument("--plaintext", action="store_true", help="เก็บรหัสผ่านแบบไม่เข้ารหัส")
    parser.add_argument("--out", default="", help="ไฟล์ CSV เก็บรหัสผ่าน (ค่าเริ่มต้นตั้งชื่อตามวันที่)")
    args = parser.parse_args()

    accounts = build_accounts()
    stations = sum(1 for a in accounts if a["role"] == "Station_Admin")
    print(f"STATION_CONFIG มี {stations} สถานี รวมบัญชีที่ควรมีทั้งหมด {len(accounts)} รายการ\n")

    try:
        rows = sheets_service.read_table(MASTER_SHEET_ID, USERS_TABLE)
    except (sheets_service.SheetNotConfigured, sheets_service.SheetWriteError) as exc:
        print(f"อ่าน {USERS_TABLE} ไม่ได้: {exc}")
        return 1

    on_sheet = read_sheet_users(rows)
    wanted = {a["username"].lower(): a for a in accounts}

    missing = [a for a in accounts if a["username"].lower() not in on_sheet]

    stale: List[Tuple[str, Dict[str, str], Dict[str, Any]]] = []
    for key, account in wanted.items():
        if key not in on_sheet:
            continue
        _, current = on_sheet[key]
        if (
            current.get("FullName") != account["fullName"]
            or current.get("Unit_ID") != account["unit"]
            or current.get("Station_ID") != account["station"]
            or current.get("Role") != account["role"]
            or current.get(ACCOUNT_TYPE_COLUMN, "") != user_service.UNIT_ACCOUNT_TYPE
        ):
            stale.append((key, current, account))

    orphans = [
        (key, line, current)
        for key, (line, current) in on_sheet.items()
        if OWNED_USERNAME.match(key) and key not in wanted
    ]

    print(f"ยังไม่มีในชีต   {len(missing)}")
    print(f"ข้อมูลไม่ตรง    {len(stale)}")
    print(f"ไม่มีสถานีรองรับ {len(orphans)}")

    for key, current, account in stale[:60]:
        changes = []
        if current.get("Unit_ID", "") != account["unit"]:
            changes.append(f"หน่วย {current.get('Unit_ID','')!r} -> {account['unit']!r}")
        if current.get(ACCOUNT_TYPE_COLUMN, "") != user_service.UNIT_ACCOUNT_TYPE:
            changes.append(f"ตั้ง {ACCOUNT_TYPE_COLUMN}={user_service.UNIT_ACCOUNT_TYPE}")
        print(f"  แก้ {key:<6} {', '.join(changes) or 'ข้อมูลสถานี'}")
    for key, line, current in orphans:
        print(f"  ลบ {key:<6} แถว {line} สถานี {current.get('Station_ID','')} {current.get('FullName','')}")

    if not (args.apply or args.sync or args.prune):
        print("\nโหมดแสดงผลอย่างเดียว — ใส่ --apply / --sync / --prune เพื่อเขียนจริง")
        return 0

    if args.apply or args.sync:
        if ensure_account_type_header(rows):
            print(f"\nเพิ่มหัวคอลัมน์ {ACCOUNT_TYPE_COLUMN} ที่ช่อง {LAST_COLUMN}1 แล้ว")
            rows = sheets_service.read_table(MASTER_SHEET_ID, USERS_TABLE)
            on_sheet = read_sheet_users(rows)

    worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, USERS_TABLE, ensure=False)

    if args.sync and stale:
        # C:F คือ FullName..Role ส่วน AccountType อยู่คอลัมน์ N ที่ไม่ติดกัน
        # ส่งเป็นสองช่วงใน batch เดียว จะได้ไม่เขียนทับคอลัมน์ G-M ที่คั่นอยู่
        updates = []
        for key, _, account in stale:
            line = on_sheet[key][0]
            updates.append({
                "range": f"C{line}:F{line}",
                "values": [[account["fullName"], account["station"], account["unit"], account["role"]]],
            })
            updates.append({
                "range": f"{LAST_COLUMN}{line}",
                "values": [[user_service.UNIT_ACCOUNT_TYPE]],
            })
        sheets_service.with_backoff(worksheet.batch_update, updates, value_input_option="RAW")
        print(f"\nอัปเดตบัญชีเดิม {len(stale)} รายการ")

    if args.prune and orphans:
        # ลบจากแถวล่างขึ้นบน ไม่งั้นเลขแถวที่เหลือจะเลื่อนหลังลบไปแล้วหนึ่งแถว
        for key, line, _ in sorted(orphans, key=lambda item: item[1], reverse=True):
            sheets_service.with_backoff(worksheet.delete_rows, line)
        print(f"ลบบัญชีที่ไม่มีสถานีรองรับ {len(orphans)} รายการ")

    if args.apply and missing:
        rows = sheets_service.read_table(MASTER_SHEET_ID, USERS_TABLE)  # อ่านใหม่ เผื่อเพิ่งลบแถวไป
        start_row = first_free_row(rows)
        values = [to_sheet_row(a, args.plaintext) for a in missing]
        end_row = start_row + len(values) - 1
        sheets_service.with_backoff(
            worksheet.update,
            range_name=f"A{start_row}:{LAST_COLUMN}{end_row}",
            values=values,
            value_input_option="RAW",
        )
        print(f"สร้างบัญชีใหม่ {len(missing)} รายการ (แถว {start_row}-{end_row})")

        out_path = args.out or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            f"credentials_{datetime.now():%Y%m%d_%H%M%S}.csv",
        )
        write_credentials_file(missing, out_path)
        print(f"รหัสผ่านตัวจริงอยู่ที่ {out_path}")
        print("ไฟล์นี้ถูก gitignore ไว้ เก็บให้ปลอดภัยและลบทิ้งเมื่อแจกรหัสครบแล้ว")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
