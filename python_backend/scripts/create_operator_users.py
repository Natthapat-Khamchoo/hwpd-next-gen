"""
สร้างบัญชีเจ้าหน้าที่ผู้ปฏิบัติ (`Unit_Staff`) ประจำสถานีในแท็บ `tb_Users`

ต่างจาก create_station_users.py ตรงที่นั่นสร้าง "บัญชีประจำหน่วย" (AccountType=Unit)
ส่วนนี่สร้าง "บัญชีของคน" จึงเว้น AccountType ไว้ ผลคือชื่อจะไปโผล่ใน dropdown
ผู้รายงาน ซึ่งเป็นพฤติกรรมที่ตั้งใจ (ดู user_service.UNIT_ACCOUNT_TYPE)

    {d}{n}   ส.ทล.{n} กก.{d}   Unit_Staff   username: op{d}{n}{ลำดับ}

`Unit_Staff` เป็น role เดียวที่ไม่อยู่ใน APPROVER_ROLES (main.py) บัญชีเหล่านี้จึง
ส่งรายงานได้แต่อนุมัติไม่ได้

ชื่อ username ขึ้นต้น op ซึ่งไม่ตรง OWNED_USERNAME ของ create_station_users.py
การรัน --prune ของสคริปต์นั้นจึงไม่มาลบบัญชีที่สร้างจากที่นี่

    python scripts/create_operator_users.py                # ดูว่าจะทำอะไร ไม่เขียนอะไร
    python scripts/create_operator_users.py --apply        # สร้างบัญชีที่ยังขาด
    python scripts/create_operator_users.py --per-station 2  # สถานีละ 2 คน

ข้อควรรู้: FullName ถูกตั้งเป็นข้อความ placeholder เพราะยังไม่มีรายชื่อจริง
ตารางนี้ออกแบบไว้ว่า 1 แถว = เจ้าหน้าที่ 1 นาย ดังนั้น placeholder เป็นของชั่วคราว
ที่ต้องตามแก้ ไม่ใช่ปลายทาง หาได้ด้วย PLACEHOLDER_PREFIX
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
    get_station_data,
)
from app.core.security import hash_password  # noqa: E402
from app.services import sheets_service, user_service  # noqa: E402

USERS_TABLE = "tb_Users"
DIVISIONS = range(1, 9)
ROLE = "Unit_Staff"

# ชื่อบัญชีที่สคริปต์นี้เป็นเจ้าของ — op + รหัสสถานีสองหลัก + ลำดับ
OWNED_USERNAME = re.compile(r"^op[1-8][1-9]\d+$")

# ทำให้ค้นเจอง่ายตอนตามเติมชื่อจริง อย่าเปลี่ยนข้อความนี้โดยไม่แก้เอกสารด้วย
PLACEHOLDER_PREFIX = "(รอระบุชื่อ)"

PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789abcdefghijkmnpqrstuvwxyz"
PASSWORD_LENGTH = 8

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
LAST_COLUMN = chr(ord("A") + len(COLUMNS) - 1)


def generate_password() -> str:
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))


def build_accounts(per_station: int) -> List[Dict[str, Any]]:
    accounts: List[Dict[str, Any]] = []
    for division in DIVISIONS:
        for station_id in get_division_stations(f"{division}0", include_hq=False):
            data = get_station_data(station_id)
            units = data.get("units") or []
            station_name = data.get("fullName", "")
            for seq in range(1, per_station + 1):
                accounts.append(
                    {
                        "username": f"op{station_id}{seq}",
                        "password": generate_password(),
                        "fullName": f"{PLACEHOLDER_PREFIX} {station_name}".strip(),
                        "station": station_id,
                        "unit": units[0] if units else "",
                        "role": ROLE,
                        "province": data.get("province", ""),
                        "stationName": station_name,
                    }
                )
    return accounts


def read_sheet_users(rows: List[List[str]]) -> Dict[str, Tuple[int, Dict[str, str]]]:
    if not rows:
        return {}
    header = [str(h).strip() for h in rows[0]]
    if "Username" not in header:
        raise SystemExit(f"ตาราง {USERS_TABLE} ไม่มีคอลัมน์ Username")

    positions = {column: header.index(column) for column in COLUMNS if column in header}
    found: Dict[str, Tuple[int, Dict[str, str]]] = {}
    for line, row in enumerate(rows[1:], start=2):
        index = positions["Username"]
        name = str(row[index]).strip() if index < len(row) else ""
        if name:
            found[name.lower()] = (
                line,
                {
                    column: (str(row[i]).strip() if i < len(row) else "")
                    for column, i in positions.items()
                },
            )
    return found


def first_free_row(rows: List[List[str]]) -> int:
    """
    แถวว่างแถวแรกโดยดูคอลัมน์ Username เท่านั้น

    ชีตมีรายการ Role ห้อยอยู่ในคอลัมน์ท้าย ๆ (แหล่งข้อมูลของ dropdown) ถ้าใช้
    append_row ตามปกติ Google จะข้ามไปต่อท้ายรายการนั้นแล้วเว้นแถวว่างกลางตารางไว้
    """
    last = 1
    for line, row in enumerate(rows[1:], start=2):
        if row and str(row[0]).strip():
            last = line
    return last + 1


def to_sheet_row(account: Dict[str, Any]) -> List[str]:
    return [
        account["username"],
        hash_password(account["username"], account["password"]),
        account["fullName"],
        account["station"],
        account["unit"],
        account["role"],
        "",  # สถานะไปช่วยราชการ
        "",  # สถานะมาช่วยราชการ
        f"บัญชีผู้ปฏิบัติ สร้าง {datetime.now():%Y-%m-%d} รอเติมชื่อจริง",
        "",  # เบอร์โทร
        "",  # รหัส
        "",  # วันที่เริ่มช่วยราชการ
        "",  # วันที่สิ้นสุดช่วยราชการ
        "",  # AccountType เว้นว่าง = บัญชีของคน ไม่ใช่บัญชีประจำหน่วย
    ]


def write_credentials_file(accounts: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Username", "Password", "Station_ID", "สถานี", "จังหวัด", "Role"])
        for account in accounts:
            writer.writerow(
                [
                    account["username"],
                    account["password"],
                    account["station"],
                    account["stationName"],
                    account["province"],
                    account["role"],
                ]
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="สร้างบัญชีเจ้าหน้าที่ผู้ปฏิบัติใน tb_Users")
    parser.add_argument("--apply", action="store_true", help="เขียนลงชีตจริง")
    parser.add_argument("--per-station", type=int, default=1, help="จำนวนบัญชีต่อสถานี (ค่าเริ่มต้น 1)")
    parser.add_argument("--out", default="", help="ไฟล์ CSV เก็บรหัสผ่าน")
    args = parser.parse_args()

    if args.per_station < 1:
        print("--per-station ต้องเป็นจำนวนเต็มบวก")
        return 1

    accounts = build_accounts(args.per_station)
    stations = len({a["station"] for a in accounts})
    print(f"{stations} สถานี x {args.per_station} คน = {len(accounts)} บัญชีที่ควรมี\n")

    try:
        rows = sheets_service.read_table(MASTER_SHEET_ID, USERS_TABLE)
    except (sheets_service.SheetNotConfigured, sheets_service.SheetWriteError) as exc:
        print(f"อ่าน {USERS_TABLE} ไม่ได้: {exc}")
        return 1

    on_sheet = read_sheet_users(rows)
    missing = [a for a in accounts if a["username"].lower() not in on_sheet]
    existing = [a for a in accounts if a["username"].lower() in on_sheet]

    print(f"มีอยู่แล้ว   {len(existing)}")
    print(f"จะสร้างใหม่  {len(missing)}")

    if missing:
        print("\nตัวอย่าง 5 รายการแรก:")
        for account in missing[:5]:
            print(f"  {account['username']:<8} {account['role']:<12} สถานี {account['station']}  {account['fullName']}")
        if len(missing) > 5:
            print(f"  ... อีก {len(missing) - 5} รายการ")

    if not args.apply:
        print("\nโหมดแสดงผลอย่างเดียว — ใส่ --apply เพื่อเขียนจริง")
        return 0

    if not missing:
        print("\nไม่มีอะไรต้องสร้าง")
        return 0

    worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, USERS_TABLE, ensure=False)
    start_row = first_free_row(rows)
    values = [to_sheet_row(a) for a in missing]
    end_row = start_row + len(values) - 1
    sheets_service.with_backoff(
        worksheet.update,
        range_name=f"A{start_row}:{LAST_COLUMN}{end_row}",
        values=values,
        value_input_option="RAW",
    )
    print(f"\nสร้างบัญชีใหม่ {len(missing)} รายการ (แถว {start_row}-{end_row})")

    out_path = args.out or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        f"credentials_operators_{datetime.now():%Y%m%d_%H%M%S}.csv",
    )
    write_credentials_file(missing, out_path)
    print(f"รหัสผ่านตัวจริงอยู่ที่ {out_path}")
    print("ไฟล์นี้ถูก gitignore ไว้ เก็บให้ปลอดภัยและลบทิ้งเมื่อแจกรหัสครบแล้ว")
    print(f"\nอย่าลืมตามเติมชื่อจริงแทน {PLACEHOLDER_PREFIX} ใน tb_Users")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
