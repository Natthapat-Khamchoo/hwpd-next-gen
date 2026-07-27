"""
สร้างบัญชีผู้ใช้ประจำสถานีและประจำกองกำกับการลงแท็บ `tb_Users` ในชีตกลาง

โครงสร้างบัญชีที่สร้าง (1 บัญชีต่อ 1 หน่วย)

    00        บก.ทล. ส่วนกลาง      Super_Commander     username: hq
    {d}0      ฝอ.กก.{d}            Division_Admin      username: fo{d}
    {d}1-{d}6 ส.ทล.1-6 กก.{d}      Station_Admin       username: st{d}{n}

รหัสผ่านสุ่มไม่ซ้ำกันต่อบัญชี เก็บลงชีตเป็น `sha256$...` (ดู core/security.py)
ส่วนรหัสตัวจริงถูกเขียนลงไฟล์ CSV บนเครื่องเท่านั้น เพื่อแจกให้แต่ละหน่วย

    python scripts/create_station_users.py              # ดูรายการที่จะสร้าง ไม่เขียนอะไร
    python scripts/create_station_users.py --apply      # เขียนลงชีตจริง
    python scripts/create_station_users.py --apply --plaintext   # เก็บรหัสแบบไม่เข้ารหัส

บัญชีที่มี Username ซ้ำกับที่มีอยู่แล้วในชีตจะถูกข้าม สคริปต์นี้จึงรันซ้ำได้
โดยไม่สร้างบัญชีซ้ำและไม่แตะบัญชีเดิม
"""

import argparse
import csv
import os
import secrets
import sys
from datetime import datetime
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import MASTER_SHEET_ID, get_station_config, get_station_data  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.services import sheets_service  # noqa: E402

USERS_TABLE = "tb_Users"
DIVISIONS = range(1, 9)
STATIONS_PER_DIVISION = 6

# ตัดตัวที่อ่านสับสนออก (0/O, 1/l/I) เพราะรหัสนี้ต้องอ่านจากกระดาษแล้วพิมพ์ตาม
PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789abcdefghijkmnpqrstuvwxyz"
PASSWORD_LENGTH = 8

# ลำดับคอลัมน์ A-M ของ tb_Users
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
]


def generate_password() -> str:
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))


def build_accounts() -> List[Dict[str, Any]]:
    """
    ประกอบรายการบัญชีจาก STATION_CONFIG

    สถานีของ กก. ที่ยังไม่มีข้อมูลจริง (กก.2, 3, 4, 6, 7, 8) จะได้ชื่อที่
    get_station_data สร้างขึ้นอัตโนมัติ การกำหนดเส้นทางฐานข้อมูลใช้ตัวเลขแรก
    ของ Station_ID จึงทำงานถูกต้องอยู่แล้ว เหลือแค่ชื่อที่ต้องมาเติมทีหลัง
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
                "known": station_id in config,
            }
        )

    add("00", "hq", "Super_Commander")

    for division in DIVISIONS:
        add(f"{division}0", f"fo{division}", "Division_Admin")
        for number in range(1, STATIONS_PER_DIVISION + 1):
            station_id = f"{division}{number}"
            add(station_id, f"st{station_id}", "Station_Admin")

    return accounts


def existing_usernames(rows: List[List[str]]) -> Dict[str, int]:
    """คืน username ที่มีอยู่แล้ว (ตัวพิมพ์เล็ก) -> เลขแถวในชีต"""
    if not rows:
        return {}
    header = [str(h).strip() for h in rows[0]]
    if "Username" not in header:
        raise SystemExit(f"ตาราง {USERS_TABLE} ไม่มีคอลัมน์ Username")
    index = header.index("Username")

    found: Dict[str, int] = {}
    for offset, row in enumerate(rows[1:], start=2):
        if index < len(row):
            name = str(row[index]).strip().lower()
            if name:
                found[name] = offset
    return found


def first_free_row(rows: List[List[str]]) -> int:
    """
    แถวว่างแถวแรกที่นับจากคอลัมน์ Username เท่านั้น

    ชีตจริงมีรายการ Role ห้อยอยู่ในคอลัมน์ท้าย ๆ (แหล่งข้อมูลของ dropdown)
    ถ้าใช้ append_row ตามปกติ Google จะข้ามไปต่อท้ายรายการนั้นแล้วเว้นแถวว่าง
    กลางตารางทิ้งไว้ จึงต้องหาตำแหน่งจากคอลัมน์ A เอง
    """
    last = 1
    for offset, row in enumerate(rows[1:], start=2):
        if row and str(row[0]).strip():
            last = offset
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
    ]


def write_credentials_file(accounts: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Username", "Password", "Station_ID", "หน่วย", "จังหวัด", "Role", "ข้อมูลสถานีจริง"])
        for account in accounts:
            writer.writerow(
                [
                    account["username"],
                    account["password"],
                    account["station"],
                    account["fullName"],
                    account["province"],
                    account["role"],
                    "ใช่" if account["known"] else "ยังไม่มี",
                ]
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="สร้างบัญชีประจำสถานีและกองกำกับการลง tb_Users")
    parser.add_argument("--apply", action="store_true", help="เขียนลงชีตจริง (ไม่ใส่ = แสดงผลอย่างเดียว)")
    parser.add_argument("--plaintext", action="store_true", help="เก็บรหัสผ่านแบบไม่เข้ารหัส")
    parser.add_argument("--out", default="", help="ไฟล์ CSV เก็บรหัสผ่าน (ค่าเริ่มต้นตั้งชื่อตามวันที่)")
    args = parser.parse_args()

    accounts = build_accounts()
    print(f"เตรียมบัญชีไว้ {len(accounts)} รายการ จาก {len(DIVISIONS)} กองกำกับการ + ส่วนกลาง\n")

    try:
        rows = sheets_service.read_table(MASTER_SHEET_ID, USERS_TABLE)
    except (sheets_service.SheetNotConfigured, sheets_service.SheetWriteError) as exc:
        print(f"อ่าน {USERS_TABLE} ไม่ได้: {exc}")
        return 1

    taken = existing_usernames(rows)
    new_accounts = [a for a in accounts if a["username"].lower() not in taken]
    skipped = [a for a in accounts if a["username"].lower() in taken]

    for account in accounts:
        mark = "ข้าม (มีอยู่แล้ว)" if account["username"].lower() in taken else ""
        print(f"  {account['username']:<6} {account['station']:<3} {account['role']:<18} {account['fullName']} {mark}")

    print(f"\nสร้างใหม่ {len(new_accounts)} บัญชี, ข้าม {len(skipped)} บัญชี")

    if not new_accounts:
        print("ไม่มีบัญชีใหม่ที่ต้องสร้าง")
        return 0

    if not args.apply:
        print("\nโหมดแสดงผลอย่างเดียว ยังไม่ได้เขียนลงชีต — ใส่ --apply เพื่อเขียนจริง")
        return 0

    start_row = first_free_row(rows)
    values = [to_sheet_row(a, args.plaintext) for a in new_accounts]
    end_row = start_row + len(values) - 1

    worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, USERS_TABLE, ensure=False)
    sheets_service.with_backoff(
        worksheet.update,
        range_name=f"A{start_row}:M{end_row}",
        values=values,
        value_input_option="RAW",
    )
    print(f"เขียนลง {USERS_TABLE} แถว {start_row}-{end_row} เรียบร้อย")

    out_path = args.out or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        f"credentials_{datetime.now():%Y%m%d_%H%M%S}.csv",
    )
    write_credentials_file(new_accounts, out_path)
    print(f"รหัสผ่านตัวจริงอยู่ที่ {out_path}")
    print("ไฟล์นี้ถูก gitignore ไว้ เก็บให้ปลอดภัยและลบทิ้งเมื่อแจกรหัสครบแล้ว")

    if not args.plaintext:
        print(f"รหัสในชีตเก็บเป็น sha256$ ต้องตั้ง PASSWORD_PEPPER ให้ตรงกันทุกเครื่องที่รันระบบ")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
