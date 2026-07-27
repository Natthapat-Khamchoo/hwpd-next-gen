"""
เปลี่ยนรหัสผ่านที่ยังเก็บเป็น plaintext ใน `tb_Users` ให้เป็น `sha256$`

**รหัสผ่านของทุกคนไม่เปลี่ยน** — เอาค่าเดิมมาเข้ารหัสทับที่เดิม เจ้าหน้าที่ยังล็อกอิน
ด้วยรหัสเดิมได้ต่อ ต่างกันแค่คนที่เปิดชีตเห็นไม่ได้อีกแล้ว

`verify_password` รองรับทั้งสองแบบอยู่แล้ว (Lazy Migration) สคริปต์นี้แค่เร่งให้จบใน
รอบเดียว แทนที่จะรอให้แต่ละคนล็อกอินเองทีละคน

    python scripts/hash_plaintext_passwords.py            # ดูว่ามีกี่บัญชี ไม่เขียนอะไร
    python scripts/hash_plaintext_passwords.py --apply    # เข้ารหัสจริง

ตรวจก่อนเขียนเสมอว่ารหัสเดิมยังผ่านการตรวจสอบด้วยค่าที่ hash แล้ว ถ้าไม่ผ่านจะหยุด
ทั้งรอบ ไม่ใช่เขียนไปครึ่งเดียวแล้วมีคนล็อกอินไม่ได้
"""

import argparse
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import MASTER_SHEET_ID  # noqa: E402
from app.core.security import hash_password, verify_password  # noqa: E402
from app.services import sheets_service, user_service  # noqa: E402

USERS_TABLE = "tb_Users"
HASH_PREFIX = "sha256$"


def collect(rows: List[List[str]]) -> List[Dict[str, Any]]:
    """หาแถวที่รหัสผ่านยังเป็น plaintext พร้อมเลขแถวและค่าที่จะเขียนแทน"""
    header = [str(h).strip() for h in rows[0]]
    for column in ("Username", "Password"):
        if column not in header:
            raise SystemExit(f"ตาราง {USERS_TABLE} ไม่มีคอลัมน์ {column}")

    name_index, password_index = header.index("Username"), header.index("Password")
    column_letter = chr(ord("A") + password_index)

    pending = []
    for line, row in enumerate(rows[1:], start=2):
        if name_index >= len(row) or password_index >= len(row):
            continue
        username = str(row[name_index]).strip()
        stored = str(row[password_index]).strip()
        if not username or not stored or stored.startswith(HASH_PREFIX):
            continue

        hashed = hash_password(username, stored)
        # กันไว้ก่อนเขียน: ค่าใหม่ต้องยืนยันรหัสเดิมผ่านจริง
        if not verify_password(username, stored, hashed):
            raise SystemExit(f"ค่าที่ hash ของบัญชี {username} ตรวจไม่ผ่าน หยุดทั้งรอบ ไม่มีการเขียนใด ๆ")

        pending.append({"username": username, "row": line, "cell": f"{column_letter}{line}", "hashed": hashed})
    return pending


def main() -> int:
    parser = argparse.ArgumentParser(description="เข้ารหัสรหัสผ่าน plaintext ใน tb_Users")
    parser.add_argument("--apply", action="store_true", help="เขียนลงชีตจริง (ไม่ใส่ = แสดงผลอย่างเดียว)")
    args = parser.parse_args()

    if not sheets_service.is_configured():
        print(sheets_service.NOT_CONFIGURED_MESSAGE)
        return 1

    rows = sheets_service.read_table(MASTER_SHEET_ID, USERS_TABLE)
    total = sum(1 for row in rows[1:] if row and str(row[0]).strip())
    pending = collect(rows)

    print(f"บัญชีทั้งหมด {total} รายการ | ยังเป็น plaintext {len(pending)} รายการ\n")
    for item in pending:
        print(f"  {item['username']:<10} แถว {item['row']:<4} -> {item['hashed'][:20]}...")

    if not pending:
        print("ไม่มีรหัสผ่าน plaintext เหลืออยู่แล้ว")
        return 0

    if not args.apply:
        print("\nโหมดแสดงผลอย่างเดียว ยังไม่ได้เขียนลงชีต — ใส่ --apply เพื่อเขียนจริง")
        print("รหัสผ่านของทุกคนจะไม่เปลี่ยน ยังล็อกอินด้วยรหัสเดิมได้ตามปกติ")
        return 0

    worksheet = sheets_service.get_worksheet(MASTER_SHEET_ID, USERS_TABLE, ensure=False)
    sheets_service.with_backoff(
        worksheet.batch_update,
        [{"range": item["cell"], "values": [[item["hashed"]]]} for item in pending],
        value_input_option="RAW",
    )
    user_service.reset_cache()

    print(f"\nเข้ารหัสแล้ว {len(pending)} บัญชี รหัสผ่านเดิมยังใช้ล็อกอินได้เหมือนเดิม")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
