"""
ให้สิทธิ์ Editor แบบระบุตัวแก่บัญชีที่ระบบใช้ กับทุกไฟล์/โฟลเดอร์ที่ระบบต้องเขียน

ตอนนี้ไฟล์หลายรายการเป็นของบัญชีอื่น และระบบเข้าถึงได้ผ่าน "ทุกคนที่มีลิงก์" เท่านั้น
ถ้าปิดการแชร์แบบเปิดโดยไม่ทำขั้นนี้ก่อน ระบบจะเข้าชีต tb_Users ไม่ได้ และล็อกอินพัง
ทั้งระบบทันที — สคริปต์นี้คือขั้นตอนที่ต้องทำ **ก่อน** เสมอ

    python scripts/grant_system_access.py            # ดูว่าต้องเพิ่มสิทธิ์ที่ไหนบ้าง
    python scripts/grant_system_access.py --apply    # เพิ่มสิทธิ์จริง
    python scripts/grant_system_access.py --verify   # ทดสอบว่าอ่าน/เขียนได้จริงทุกไฟล์

สคริปต์นี้ **ไม่ถอด** สิทธิ์ "ทุกคนที่มีลิงก์" ออก การปิดเป็นคนละขั้นและต้องรู้ก่อนว่า
มีใครใช้ลิงก์นั้นอยู่บ้าง (ดู docs/deploy-render.md)
"""

import argparse
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import MASTER_SHEET_ID, get_db_router, get_division_folders  # noqa: E402
from app.services import sheets_service  # noqa: E402

TEMPLATE_KEYS = ("AUTO_ARREST_DOC_ID", "AUTO_ARREST_M22_ID", "AUTO_ARREST_FOLDER_ID")


def _drive():
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=sheets_service.get_credentials(), cache_discovery=False)


def system_account(drive) -> str:
    """อีเมลของบัญชีที่ credentials ชุดนี้ทำงานในนาม"""
    return drive.about().get(fields="user(emailAddress)").execute()["user"]["emailAddress"]


def targets() -> List[Dict[str, str]]:
    items = [{"label": "ชีตกลาง (tb_Users, tb_Charges)", "id": MASTER_SHEET_ID}]
    for division, entry in sorted(get_db_router().items()):
        if entry.get("OPS"):
            items.append({"label": f"ฐานข้อมูล กก.{division}", "id": entry["OPS"]})
    for division, folder_id in sorted(get_division_folders().items()):
        items.append({"label": f"โฟลเดอร์ไฟล์แนบ กก.{division}", "id": folder_id})
    for key in TEMPLATE_KEYS:
        if os.getenv(key, "").strip():
            items.append({"label": key, "id": os.getenv(key).strip()})
    return items


def inspect(drive, item: Dict[str, str], account: str) -> Dict[str, Any]:
    meta = drive.files().get(
        fileId=item["id"], supportsAllDrives=True,
        fields="id,name,mimeType,owners(emailAddress),capabilities(canShare)",
    ).execute()
    perms = drive.permissions().list(
        fileId=item["id"], supportsAllDrives=True,
        fields="permissions(id,type,role,emailAddress)",
    ).execute().get("permissions", [])

    owner = (meta.get("owners") or [{}])[0].get("emailAddress", "")
    direct = next(
        (p for p in perms if p["type"] == "user" and p.get("emailAddress", "").lower() == account.lower()),
        None,
    )
    return {
        **item,
        "name": meta.get("name", ""),
        "owner": owner,
        "isOwner": owner.lower() == account.lower(),
        "directRole": direct["role"] if direct else "",
        "canShare": meta.get("capabilities", {}).get("canShare", False),
        "publicRole": next((p["role"] for p in perms if p["type"] == "anyone"), ""),
    }


def grant(drive, file_id: str, account: str) -> None:
    drive.permissions().create(
        fileId=file_id,
        body={"type": "user", "role": "writer", "emailAddress": account},
        supportsAllDrives=True,
        sendNotificationEmail=False,
    ).execute()


def verify(drive, item: Dict[str, str]) -> str:
    """ยืนยันว่าเข้าถึงได้จริง ไม่ใช่แค่เห็นว่ามีสิทธิ์ในหน้าตั้งค่า"""
    try:
        meta = drive.files().get(
            fileId=item["id"], supportsAllDrives=True,
            fields="mimeType,capabilities(canEdit)",
        ).execute()
    except Exception as exc:
        return f"เข้าไม่ได้: {str(exc)[:60]}"

    if not meta.get("capabilities", {}).get("canEdit"):
        return "อ่านได้แต่แก้ไขไม่ได้"

    if meta["mimeType"] == "application/vnd.google-apps.spreadsheet":
        try:
            sheets_service.open_spreadsheet(item["id"]).worksheets()
        except Exception as exc:
            return f"เปิดเป็นสเปรดชีตไม่ได้: {str(exc)[:60]}"
    return "ผ่าน"


def main() -> int:
    parser = argparse.ArgumentParser(description="ให้สิทธิ์ Editor แก่บัญชีที่ระบบใช้")
    parser.add_argument("--apply", action="store_true", help="เพิ่มสิทธิ์จริง")
    parser.add_argument("--verify", action="store_true", help="ทดสอบการเข้าถึงหลังเพิ่มสิทธิ์")
    parser.add_argument("--account", default="", help="อีเมลที่จะให้สิทธิ์ (ค่าเริ่มต้น = บัญชีของ credentials)")
    args = parser.parse_args()

    if not sheets_service.is_configured():
        print(sheets_service.NOT_CONFIGURED_MESSAGE)
        return 1

    drive = _drive()
    account = args.account.strip() or system_account(drive)
    print(f"บัญชีที่ระบบทำงานในนาม: {account}\n")

    rows = [inspect(drive, item, account) for item in targets()]
    needed = [r for r in rows if not r["isOwner"] and not r["directRole"]]
    blocked = [r for r in needed if not r["canShare"]]

    print(f"{'รายการ':<30} {'สถานะสิทธิ์':<22} เจ้าของ")
    print("-" * 92)
    for r in rows:
        if r["isOwner"]:
            status = "เป็นเจ้าของอยู่แล้ว"
        elif r["directRole"]:
            status = f"มีสิทธิ์ตรงแล้ว ({r['directRole']})"
        else:
            status = "** ต้องเพิ่มสิทธิ์ **"
        print(f"{r['label']:<30} {status:<22} {r['owner']}")

    public = [r for r in rows if r["publicRole"]]
    print(f"\nต้องเพิ่มสิทธิ์ {len(needed)} รายการ | ยังเปิดให้ทุกคนที่มีลิงก์ {len(public)} รายการ")

    if blocked:
        print("\nแก้การแชร์เองไม่ได้ ต้องให้เจ้าของทำให้:")
        for r in blocked:
            print(f"  - {r['label']} ({r['name']}) เจ้าของ {r['owner']}")

    if args.apply and needed:
        print()
        for r in needed:
            if not r["canShare"]:
                print(f"  ข้าม {r['label']} (ไม่มีสิทธิ์แก้การแชร์)")
                continue
            try:
                grant(drive, r["id"], account)
                print(f"  เพิ่มสิทธิ์ Editor ให้ {account} ที่ {r['label']} แล้ว")
            except Exception as exc:
                print(f"  ล้มเหลว {r['label']}: {str(exc)[:80]}")

    if args.verify:
        print("\nทดสอบการเข้าถึงจริง:")
        failures = 0
        for r in rows:
            result = verify(drive, r)
            if result != "ผ่าน":
                failures += 1
            print(f"  {r['label']:<30} {result}")
        print(f"\nผ่าน {len(rows) - failures} / ไม่ผ่าน {failures}")
        return 1 if failures else 0

    if not (args.apply or args.verify):
        print("\nโหมดแสดงผลอย่างเดียว — ใส่ --apply เพื่อเพิ่มสิทธิ์ หรือ --verify เพื่อทดสอบการเข้าถึง")

    if public:
        print(
            "\nยังไม่ได้ปิดการแชร์แบบ 'ทุกคนที่มีลิงก์' และสคริปต์นี้ไม่ปิดให้ "
            "ก่อนปิดต้องแชร์ตรงให้ทุกคนที่ใช้ลิงก์อยู่ก่อน ไม่งั้นจะถูกตัดสิทธิ์ทันที"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
