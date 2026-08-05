"""
ตรวจความพร้อมของทั้ง 8 กองกำกับการ ก่อนเปิดใช้งานจริง

## ทำไมต้องมี

ระบบถูกพัฒนาและทดสอบกับ กก.5 เป็นหลัก แล้วค่อยขยายไปกองอื่น ของที่ "ทำงานได้"
จึงมักหมายถึง "ทำงานได้กับ กก.5" การไล่เปิดทีละหน้าเพื่อดูว่ากองอื่นพร้อมไหมใช้เวลานาน
และมองข้ามได้ง่าย เพราะหน้าจอที่ไม่มีข้อมูลกับหน้าจอที่พังดูเหมือนกัน

สคริปต์นี้ตรวจของที่ต้องมีครบก่อนกองนั้นจะใช้งานได้จริง แล้วบอกว่าขาดอะไร
**อ่านอย่างเดียว ไม่เขียนอะไรทั้งสิ้น** รันซ้ำได้ตลอด

    cd python_backend
    python scripts/check_division_readiness.py
    python scripts/check_division_readiness.py --divisions 1,8

รหัสออก: 0 = พร้อมทุกกอง, 1 = มีกองที่ยังขาดของจำเป็น
"""

import argparse
import datetime
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import (  # noqa: E402
    MASTER_SHEET_ID,
    get_db_router,
    get_division_folder_id,
    get_division_stations,
    get_station_data,
)
from app.core.schema import TABLE_COLUMNS  # noqa: E402
from app.services import sheets_service, user_service  # noqa: E402

# ตารางที่กองหนึ่งต้องมีจึงจะใช้งานได้ครบทุกฟอร์ม ไม่รวมตารางของชีตกลาง
DIVISION_TABLES = [
    t for t in TABLE_COLUMNS
    if t not in ("tb_National_Summary", "tb_Charges", "tb_ReportCatalog", "tb_Users", "tb_PR_Keywords")
]

# ของที่ขาดแล้วกองนั้นใช้งานไม่ได้เลย แยกจากของที่ขาดแล้วแค่ใช้งานได้ไม่ครบ
BLOCKING = "ต้องมี"
WARNING = "ควรมี"


class Report:
    def __init__(self):
        self.rows = defaultdict(list)

    def add(self, division, level, message):
        self.rows[division].append((level, message))

    def blocking(self, division):
        return [m for lvl, m in self.rows[division] if lvl == BLOCKING]

    def warnings(self, division):
        return [m for lvl, m in self.rows[division] if lvl == WARNING]


def check_sheet(division, sheet_id, report):
    """สเปรดชีตเปิดได้ไหม และมีแท็บครบไหม"""
    try:
        spreadsheet = sheets_service.open_spreadsheet(sheet_id)
    except Exception as exc:  # noqa: BLE001
        report.add(division, BLOCKING, f"เปิดสเปรดชีตไม่ได้: {type(exc).__name__}: {str(exc)[:60]}")
        return

    existing = {ws.title for ws in sheets_service.with_backoff(spreadsheet.worksheets)}
    missing = [t for t in DIVISION_TABLES if t not in existing]
    if missing:
        # แท็บที่ยังไม่มีจะถูกสร้างเองตอนบันทึกครั้งแรก จึงไม่ถึงขั้นใช้งานไม่ได้
        report.add(division, WARNING, f"ยังไม่มีแท็บ {len(missing)} ตาราง: {', '.join(missing[:4])}"
                                      + (" ..." if len(missing) > 4 else ""))


def check_folder(division, report):
    """โฟลเดอร์ไฟล์แนบตั้งไว้ไหม และไม่ได้เปิดสาธารณะอยู่"""
    folder = get_division_folder_id(f"{division}1")
    if not folder:
        report.add(division, BLOCKING, "ยังไม่ได้ตั้งโฟลเดอร์ไฟล์แนบ (DIVISION_FOLDERS_JSON) — แนบไฟล์แล้วจะหาย")
        return

    try:
        from app.services import storage_service

        perms = storage_service.drive_service().permissions().list(
            fileId=folder, fields="permissions(type,role)", supportsAllDrives=True
        ).execute().get("permissions", [])
    except Exception as exc:  # noqa: BLE001
        report.add(division, BLOCKING, f"เปิดโฟลเดอร์ไฟล์แนบไม่ได้: {type(exc).__name__}")
        return

    public = [p for p in perms if p.get("type") in ("anyone", "domain")]
    if public:
        shape = ", ".join(f"{p['type']}/{p['role']}" for p in public)
        report.add(division, BLOCKING, f"โฟลเดอร์ไฟล์แนบยังเปิดสาธารณะอยู่ ({shape}) — รัน lock_drive_sharing.py")


def check_users(division, users_by_division, report):
    """มีบัญชีให้ใช้งานครบทุกระดับไหม"""
    accounts = users_by_division.get(division, [])
    if not accounts:
        report.add(division, BLOCKING, "ไม่มีบัญชีผู้ใช้เลยสักคน — รัน create_station_users.py --apply")
        return

    roles = {a["role"] for a in accounts}
    for role, label in (("Division_Admin", "ฝอ.กก."), ("Division_Commander", "ผกก.")):
        if role not in roles:
            report.add(division, WARNING, f"ยังไม่มีบัญชี {label} ({role})")
    if not any(r in roles for r in ("Station_Admin", "สิบเวร")):
        report.add(division, WARNING, "ยังไม่มีบัญชีระดับสถานีเลย ไม่มีใครอนุมัติรายงานได้")

    placeholders = [a for a in accounts if "รอระบุชื่อ" in str(a.get("fullName", ""))]
    if placeholders:
        report.add(division, WARNING, f"มีบัญชีที่ยังไม่ได้ใส่ชื่อจริง {len(placeholders)} บัญชี")


def check_stations(division, report):
    """รายชื่อสถานีกับการตั้งค่ารายสถานี"""
    stations = get_division_stations(f"{division}0")
    if not stations:
        report.add(division, BLOCKING, "ไม่มีรายชื่อสถานีใน STATION_SECRETS_JSON — หน้า ฝอ.กก. จะว่างเปล่า")
        return

    no_line = [s for s in stations if not get_station_data(s).get("lineGroupId")]
    if no_line:
        report.add(
            division, WARNING,
            f"ยังไม่ได้ผูกกลุ่ม LINE {len(no_line)}/{len(stations)} สถานี ({', '.join(no_line[:6])}"
            + (" ..." if len(no_line) > 6 else "") + ") — แจ้งเตือนและการสั่งการจะไม่ถึงปลายทาง",
        )


def probe_api(division, report):
    """
    ยิง endpoint ที่หน้าจอของกองนั้นเรียกจริง ด้วยบทบาทที่ใช้จริง

    ตรวจ config ครบไม่ได้แปลว่าหน้าจอเปิดได้ ที่ผ่านมาระบบพัฒนากับ กก.5 เป็นหลัก
    โค้ดที่เผลออ้างอิงอะไรเฉพาะกองจะโผล่ตรงนี้ ไม่ใช่ตอนผู้ใช้กองอื่นเปิดหน้าจอเอง
    """
    from fastapi.testclient import TestClient

    from app import main as app_main
    from app.core.security import create_session_token

    client = TestClient(app_main.app, raise_server_exceptions=False)
    hq = {"x-token": create_session_token({"username": f"fo{division}", "role": "Division_Admin", "station": f"{division}0"})}
    cmd = {"x-token": create_session_token({"username": f"pk{division}", "role": "Division_Commander", "station": f"{division}0"})}
    st = {"x-token": create_session_token({"username": f"st{division}1", "role": "Station_Admin", "station": f"{division}1"})}

    today, start = datetime.date.today().isoformat(), (datetime.date.today() - datetime.timedelta(days=29)).isoformat()
    cases = [
        ("ภาพรวม กก.", f"/api/division-summary?station={division}0&start={start}&end={today}", hq),
        ("รายละเอียดรายวัน", f"/api/hq/daily-detail?station={division}0&date={today}", hq),
        ("น้ำมัน", f"/api/hq/fuel?station={division}0&monthYear={today[:7]}", hq),
        ("กำลังพล", f"/api/hq/manpower?station={division}0", hq),
        ("ของกลาง", f"/api/hq/evidence?station={division}0", hq),
        ("นำขบวน", f"/api/hq/escort?station={division}0&start={start}&end={today}", hq),
        ("แผนที่", f"/api/map/points?station={division}0&start={start}&end={today}", hq),
        ("ภาพรวม ผกก.", f"/api/commander/overview?station={division}0", cmd),
        ("สรุป ผกก.", f"/api/commander/summary?station={division}0", cmd),
        ("คิวอนุมัติสถานี", f"/api/station-pending?station={division}1", st),
        ("ข่าว ปชส.", f"/api/pr/news?station={division}0", hq),
        ("รายงานค้าง ปชส.", f"/api/pr/report/pending?station={division}0", hq),
    ]

    for label, path, token in cases:
        response = client.get(path, headers=token)
        if response.status_code != 200:
            detail = ""
            try:
                body = response.json()
                detail = str(body.get("detail") or body.get("message") or "")[:60]
            except Exception:  # noqa: BLE001
                detail = response.text[:60]
            report.add(division, BLOCKING, f"{label} ตอบ {response.status_code} {detail}")
            continue
        # บาง endpoint คืน array เปล่า ๆ ไม่ใช่ {status:...} จึงเช็คเฉพาะตัวที่เป็น object
        try:
            body = response.json()
        except Exception:  # noqa: BLE001
            report.add(division, BLOCKING, f"{label} ตอบ 200 แต่ไม่ใช่ JSON")
            continue
        if isinstance(body, dict) and body.get("status") == "error":
            report.add(division, BLOCKING, f"{label} ตอบ 200 พร้อม status error: {str(body.get('message'))[:60]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="ตรวจความพร้อมรายกองกำกับการ")
    parser.add_argument("--divisions", default="", help="เลข กก. คั่นด้วยลูกน้ำ เว้นว่าง = ทุกกอง")
    parser.add_argument("--probe", action="store_true",
                        help="ยิง endpoint ของหน้าจอจริงด้วย (ช้ากว่า เพราะอ่านชีตทุกกอง)")
    args = parser.parse_args()

    router = get_db_router()
    wanted = [d.strip() for d in args.divisions.split(",") if d.strip()] or [str(d) for d in range(1, 9)]
    report = Report()

    # อ่านบัญชีทีเดียวแล้วแยกตามกอง ดีกว่าอ่านซ้ำแปดรอบซึ่งจะชน 429 ของ Google
    users_by_division = defaultdict(list)
    try:
        for account in user_service.get_all_users().values():
            station = str(account.get("station") or "")
            if station[:1].isdigit():
                users_by_division[station[:1]].append(account)
    except Exception as exc:  # noqa: BLE001
        print(f"อ่าน tb_Users ไม่ได้: {type(exc).__name__}: {str(exc)[:70]}\n")

    print(f"ตรวจความพร้อม {len(wanted)} กองกำกับการ (อ่านอย่างเดียว)")
    print("=" * 74)

    for division in wanted:
        sheet_id = (router.get(division) or {}).get("OPS", "")
        if not sheet_id:
            report.add(division, BLOCKING, "ยังไม่ได้ตั้ง DB_ROUTER — กองนี้ใช้งานไม่ได้เลย")
        else:
            check_sheet(division, sheet_id, report)
        check_folder(division, report)
        check_users(division, users_by_division, report)
        check_stations(division, report)
        if args.probe:
            probe_api(division, report)

        blockers, warns = report.blocking(division), report.warnings(division)
        mark = "พร้อม" if not blockers else "ยังไม่พร้อม"
        print(f"\nกก.{division}  [{mark}]  บัญชี {len(users_by_division.get(division, []))} คน")
        for message in blockers:
            print(f"   ! {message}")
        for message in warns:
            print(f"   - {message}")
        if not blockers and not warns:
            print("   ครบทุกอย่าง")

    print("\n" + "=" * 74)
    not_ready = [d for d in wanted if report.blocking(d)]
    if not_ready:
        print(f"ยังไม่พร้อม {len(not_ready)} กอง: {', '.join('กก.' + d for d in not_ready)}")
        return 1
    total_warnings = sum(len(report.warnings(d)) for d in wanted)
    print(f"พร้อมใช้งานทุกกอง — มีข้อควรทำเพิ่มอีก {total_warnings} รายการ (ขึ้นต้นด้วย -)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
