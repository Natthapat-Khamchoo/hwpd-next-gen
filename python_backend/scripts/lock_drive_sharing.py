"""
ปิดการแชร์แบบ "ทุกคนที่มีลิงก์" ของสเปรดชีตและโฟลเดอร์ไฟล์แนบทั้งระบบ

## ทำไมต้องมีสคริปต์นี้

ตรวจเมื่อ 5 ส.ค. 2569 พบว่าสเปรดชีตปฏิบัติการทั้ง 8 กอง ชีตกลาง และโฟลเดอร์ไฟล์แนบ
ทั้ง 8 กอง ถูกตั้งเป็น `anyone / writer` — ใครก็ตามที่มีลิงก์ **แก้ไขได้** ไม่ใช่แค่อ่าน

ผลที่หนักที่สุดไม่ใช่ข้อมูลรั่ว แต่คือการข้ามระบบล็อกอินทั้งระบบ ชีตกลางเก็บแท็บ
`tb_Users` ซึ่งมีคอลัมน์ `Password` กับ `Role` และ `verify_password` ยังรองรับรหัสผ่าน
แบบ plaintext ไว้สำหรับบัญชีเก่า (`core/security.py`) คนที่มีลิงก์จึงพิมพ์รหัสผ่านลง
ช่อง Password ของบัญชีใดก็ได้ เปลี่ยน Role เป็น `Super_Commander` แล้วล็อกอินเข้ามา
เป็นคนนั้นได้ทันที โดยไม่ต้องเจาะอะไรเลย

## สคริปต์นี้ทำอะไร

ลบเฉพาะ permission ชนิด `anyone` ออกจากไฟล์และโฟลเดอร์ที่ระบบใช้งาน **ไม่แตะสิทธิ์
ของคนที่ได้รับเชิญไว้เป็นรายบุคคล และไม่แตะเจ้าของไฟล์** บัญชีที่ระบบใช้ทำงาน
(ตัวที่ถือ OAuth token) ได้สิทธิ์มาแบบรายบุคคลอยู่แล้ว ระบบจึงทำงานต่อได้ตามปกติ

**สิ่งที่จะพังหลังรัน** คือการเปิดชีตด้วยลิงก์ตรงของคนที่ไม่ได้ถูกเชิญไว้ ใครที่ยังต้อง
เปิดชีตเองต้องถูกเพิ่มเป็นรายบุคคลก่อน สคริปต์จึงพิมพ์รายชื่อผู้ที่จะยังเข้าได้ให้ดู
ก่อนเสมอ

    cd python_backend
    python scripts/lock_drive_sharing.py            # ดูอย่างเดียว ไม่แก้อะไร
    python scripts/lock_drive_sharing.py --apply    # ปิดจริง
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import (  # noqa: E402
    MASTER_SHEET_ID,
    get_db_router,
    get_division_folder_id,
)
from app.services import storage_service  # noqa: E402


def targets():
    """ไฟล์และโฟลเดอร์ทุกตัวที่ระบบใช้งาน คู่กับป้ายที่คนอ่านเข้าใจ"""
    items = [("ชีตกลาง (tb_Users, tb_Charges ฯลฯ)", MASTER_SHEET_ID)]
    for division, entry in sorted(get_db_router().items()):
        if entry.get("OPS"):
            items.append((f"สเปรดชีตปฏิบัติการ กก.{division}", entry["OPS"]))
    for division in "12345678":
        folder = get_division_folder_id(f"{division}1")
        if folder:
            items.append((f"โฟลเดอร์ไฟล์แนบ กก.{division}", folder))
    return items


def ancestors(service, file_id, limit=8):
    """ไล่จากไฟล์ขึ้นไปหาโฟลเดอร์แม่จนสุดสาย คืน [(id, ชื่อ), ...] จากล่างขึ้นบน"""
    chain, current, depth = [], file_id, 0
    while current and depth < limit:
        meta = service.files().get(
            fileId=current, fields="id,name,parents", supportsAllDrives=True
        ).execute()
        chain.append((meta["id"], meta.get("name") or "(ไม่มีชื่อ)"))
        parents = meta.get("parents") or []
        current = parents[0] if parents else None
        depth += 1
    return chain


def public_permissions(service, file_id):
    return [
        p
        for p in service.permissions().list(
            fileId=file_id, fields="permissions(id,type,role)", supportsAllDrives=True
        ).execute().get("permissions", [])
        if p.get("type") in ("anyone", "domain")
    ]


def sharing_roots(service, items):
    """
    หา "ต้นทางจริง" ของการแชร์สาธารณะ

    Drive ไม่ยอมให้ลบ permission ที่สืบทอดมาจากโฟลเดอร์แม่ (403 cannotDeletePermission)
    ไฟล์สิบเจ็ดรายการของระบบนี้อยู่ใต้โฟลเดอร์เดียวกันหมด การไล่ลบทีละไฟล์จึงล้มทุกอัน
    ต้องขึ้นไปปิดที่โฟลเดอร์บนสุดที่ยังถือ permission นั้นอยู่ ปิดที่เดียวได้ผลทั้งสาย
    """
    roots = {}
    for label, file_id in items:
        for node_id, name in ancestors(service, file_id):
            if public_permissions(service, node_id):
                roots.setdefault(node_id, {"name": name, "covers": []})
                roots[node_id]["covers"].append(label)
    # เก็บเฉพาะโหนดบนสุดของแต่ละสาย — โหนดที่ครอบของมากที่สุดคือโหนดที่อยู่บนสุด
    return dict(sorted(roots.items(), key=lambda kv: -len(kv[1]["covers"])))


def describe(service, file_id):
    """คืน (สิทธิ์สาธารณะที่พบ, คนที่จะยังเข้าได้หลังปิด)"""
    perms = service.permissions().list(
        fileId=file_id,
        fields="permissions(id,type,role,emailAddress,displayName)",
        supportsAllDrives=True,
    ).execute().get("permissions", [])

    public = [p for p in perms if p.get("type") in ("anyone", "domain")]
    keeps = [
        f"{p.get('emailAddress') or p.get('displayName') or p['type']} ({p['role']})"
        for p in perms
        if p.get("type") not in ("anyone", "domain")
    ]
    return public, keeps


def main() -> int:
    parser = argparse.ArgumentParser(description="ปิดการแชร์แบบทุกคนที่มีลิงก์")
    parser.add_argument("--apply", action="store_true", help="ปิดจริง (ไม่ใส่ = ดูอย่างเดียว)")
    args = parser.parse_args()

    service = storage_service.drive_service()
    items = targets()
    print(f"ตรวจ {len(items)} รายการ" + ("" if args.apply else "  (โหมดดูอย่างเดียว)"))
    print("=" * 78)

    to_fix, failed = [], []
    for label, file_id in items:
        try:
            public, keeps = describe(service, file_id)
        except Exception as exc:  # noqa: BLE001
            print(f"  [อ่านไม่ได้] {label}: {type(exc).__name__}: {exc}")
            failed.append(label)
            continue

        if not public:
            print(f"  [ปิดอยู่แล้ว] {label}")
            continue

        shape = ", ".join(f"{p['type']}/{p['role']}" for p in public)
        print(f"  [ต้องปิด]    {label}  <-  {shape}")
        print(f"               หลังปิดยังเข้าได้: {', '.join(keeps) or '(ไม่มีใครเลย!)'}")
        to_fix.append((label, file_id, public, keeps))

    print("=" * 78)

    # ไม่มีใครเหลือเลยแปลว่าปิดแล้วจะไม่มีทางเข้าถึงไฟล์นั้นอีก รวมถึงตัวระบบเอง
    orphans = [label for label, _fid, _pub, keeps in to_fix if not keeps]
    if orphans:
        print("หยุด: ไฟล์ข้างล่างจะไม่เหลือใครเข้าถึงได้เลยหลังปิด ต้องเพิ่มสิทธิ์รายบุคคลก่อน")
        for label in orphans:
            print("   -", label)
        return 2

    if not to_fix:
        print("ทุกรายการปิดเรียบร้อยอยู่แล้ว ไม่มีอะไรต้องทำ")
        return 0

    if not args.apply:
        print(f"ต้องปิด {len(to_fix)} รายการ — รันซ้ำด้วย --apply เพื่อปิดจริง")
        return 0

    # ปิดที่ "ต้นทาง" ไม่ใช่ที่ตัวไฟล์
    #
    # Drive ไม่ยอมให้ลบ permission ที่สืบทอดมาจากโฟลเดอร์แม่ (403 cannotDeletePermission)
    # รอบแรกที่เขียนสคริปต์นี้ไล่ลบทีละไฟล์แล้วล้มครบทั้งสิบเจ็ดรายการ
    roots = sharing_roots(service, [(label, fid) for label, fid, _p, _k in to_fix])
    print(f"\nต้นทางของการแชร์ {len(roots)} จุด:")
    for node_id, info in roots.items():
        print(f"   {info['name']}  [{node_id}]  ครอบคลุม {len(info['covers'])} รายการ")
    print()

    removed = 0
    for node_id, info in roots.items():
        for permission in public_permissions(service, node_id):
            shape = f"{permission['type']}/{permission['role']}"
            try:
                service.permissions().delete(
                    fileId=node_id, permissionId=permission["id"], supportsAllDrives=True
                ).execute()
                removed += 1
                print(f"  [ปิดแล้ว]      {info['name']}  ({shape})")
            except Exception as exc:  # noqa: BLE001
                print(f"  [ปิดไม่สำเร็จ] {info['name']} ({shape}): {type(exc).__name__}: {str(exc)[:110]}")
                failed.append(info["name"])

    print(f"\nปิดสิทธิ์สาธารณะไปทั้งหมด {removed} รายการ")
    if failed:
        print(f"ยังมีที่ทำไม่สำเร็จ {len(set(failed))} รายการ ต้องตามแก้ด้วยมือ")
        return 1
    print("ตรวจซ้ำได้ด้วยการรันสคริปต์นี้อีกครั้งโดยไม่ใส่ --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
