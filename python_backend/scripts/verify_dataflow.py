"""
ตรวจว่าข้อมูลจากฟอร์มไหลไปลงชีตของแต่ละ กก. ถูกต้องหรือไม่

สคริปต์นี้ยิงผ่าน API จริงและเขียนแถวทดสอบลงชีตจริง จึงควรใช้กับฐานข้อมูลทดสอบ
เท่านั้น ใส่ --cleanup เพื่อลบแถวที่สคริปต์เขียนเองออกเมื่อตรวจเสร็จ

    cd python_backend
    python scripts/verify_dataflow.py                  # ตรวจทั้ง 8 กก. แล้วเก็บแถวไว้ให้ดู
    python scripts/verify_dataflow.py --cleanup        # ตรวจแล้วลบแถวทดสอบทิ้ง
    python scripts/verify_dataflow.py --divisions 1,5  # ตรวจเฉพาะบาง กก.
    python scripts/verify_dataflow.py --report-types daily,fuel   # ตรวจเฉพาะบางฟอร์ม

สิ่งที่ตรวจ:
  ส่วนที่ 1  ระบบล็อกอินและการปฏิเสธที่ควรเกิด (ไม่เขียนข้อมูล)
  ส่วนที่ 2  ส่งรายงานทุกประเภทที่รองรับ จากทุก กก. ผ่าน API
  ส่วนที่ 3  อ่านกลับจากชีตแต่ละไฟล์ ยืนยันว่าลงถูกไฟล์ ถูกคอลัมน์ และไม่ปนข้าม กก.
  ส่วนที่ 4  ส่งรายงานพร้อมไฟล์แนบ ยืนยันว่าไฟล์ขึ้นโฟลเดอร์ Drive ของ กก. นั้นจริง
"""

import argparse
import base64
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.core.config  # noqa: E402,F401 — โหลด .env
from app.core.config import get_db_router, get_division_folders  # noqa: E402
from app.core.schema import get_columns  # noqa: E402
from app.core.security import create_session_token  # noqa: E402
from app.services import sheets_service  # noqa: E402

MARKER = "VERIFY-DATAFLOW"
REPORT_TABLES = {
    "daily": "tb_DailyReport",
    "daily-result": "tb_DailyResult",
    "station-duty": "tb_StationDuty",
    "other-duty": "tb_OtherDuties",
    "checkpoint": "tb_Checkpoints",
    "arrest": "tb_Arrests",
    "accident": "tb_Accidents",
    "mission": "tb_Missions",
    "royal-guard": "tb_RoyalGuard",
    "fuel": "tb_FuelOil",
    "document": "tb_Documents",
}
# ฟอร์มที่หน้าเว็บมีแต่ backend ยังไม่มี endpoint รองรับ
UNIMPLEMENTED = ["daily-summary", "mission-summary", "auto-arrest"]

results: List[Dict[str, Any]] = []


def record(section: str, label: str, ok: bool, detail: str = "") -> bool:
    results.append({"section": section, "label": label, "ok": ok, "detail": detail})
    print(("  PASS  " if ok else "  FAIL  ") + label + (f"   [{detail}]" if detail and not ok else ""))
    return ok


def with_retry(fn, *args, attempts: int = 4, **kwargs):
    """Sheets API จำกัดจำนวนคำขอต่อนาที เจอ 429 ให้รอแล้วลองใหม่"""
    for attempt in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            if "429" not in str(exc) or attempt == attempts - 1:
                raise
            wait = 15 * (attempt + 1)
            print(f"    (โดน rate limit รอ {wait} วินาทีแล้วลองใหม่)")
            time.sleep(wait)


def payload_for(kind: str, division: str, station: str) -> Dict[str, Any]:
    base = {
        "stationId": station,
        "unitId": f"หน่วยฯทดสอบ กก.{division}",
        "unitName": f"หน่วยบริการฯทดสอบ กก.{division}",
        "actionBy": f"verify_kk{division}",
        "reportDateTime": "2026-07-26T09:00",
    }

    if kind == "daily":
        return {
            "formData": {
                **base,
                "dutyOfficer": f"ด.ต. {MARKER} กก.{division}",
                "dutyPhone": f"08{division}1111111"[:10],
                "carNumber": f"ทล.{station}01",
                "driverName": f"ส.ต.อ. พลขับ กก.{division}",
                "driverPhone": f"08{division}2222222"[:10],
                "radioOpName": f"จ.ส.ต. พงว. กก.{division}",
                "radioOpPhone": f"08{division}3333333"[:10],
                "startTime": "2026-07-26",
                "endTime": "2026-07-27",
                "camTotal": int(division) + 3,
                "camReady": int(division) + 2,
                "camBroken": 1,
            }
        }

    if kind == "checkpoint":
        return {
            "formData": {
                **base,
                "dutyOfficer": f"ร.ต.อ. {MARKER} กก.{division}",
                "totalPersonnel": int(division) + 1,
                "carNumber": f"ทล.{station}02",
                "location": f"ทล.{division} กม.{division}0 จุดตรวจทดสอบ",
            }
        }

    if kind == "daily-result":
        return {
            "formData": {
                **base,
                "v43": int(division) * 10,
                "service": int(division) * 5,
                "v42": int(division) * 2,
                "v20": int(division) * 3,
                "camTotal2": 4, "camReady2": 3, "camBroken2": 1,
                "searchTarget": int(division),
            },
            "charges": [{"name": "ขับรถเร็วเกินกำหนด", "amount": int(division)}],
        }

    if kind == "station-duty":
        return {
            "formData": {
                **base,
                "inspectorName": f"ร.ต.อ. ร้อยเวร กก.{division}",
                "inspectorPhone": f"08{division}4444444"[:10],
                "dutyOfficerName": f"ด.ต. สิบเวร กก.{division}",
                "dutyOfficerPhone": f"08{division}5555555"[:10],
                "radioOpName": f"จ.ส.ต. พงว. กก.{division}",
                "radioOpPhone": f"08{division}6666666"[:10],
                "startTime": "2026-07-26",
                "endTime": "2026-07-27",
            }
        }

    if kind == "other-duty":
        return {
            "formData": {
                **base,
                "carNumber": f"ทล.{station}03",
                "dutyType": "ทำจิตอาสา",
                "actionDetails": f"{MARKER} จิตอาสาทดสอบ กก.{division}",
                "location": f"ทล.{division} กม.{division}1",
                "volType": "พัฒนา",
                "volPolice": int(division),
            },
            "officers": [f"ด.ต. จิตอาสา กก.{division}"],
        }

    if kind == "accident":
        return {
            "formData": {
                **base,
                "route": division, "km": f"{division}5", "direction": "ขาเข้า",
                "locDetails": f"{MARKER} จุดเกิดเหตุทดสอบ",
                "deadCount": 0, "injuredCount": int(division), "hospital": f"รพ.ทดสอบ {division}",
                "mainVehicle": "รถยนต์", "oppVehicle": "รถจักรยานยนต์",
                "cHuman": 70, "cVehicle": 10, "cRoad": 10, "cEnv": 10,
                "solutions": "ติดตั้งป้ายเตือน",
                "govDamage": "ไม่มี",
                "carNumber": f"ทล.{station}04",
                "jointUnits": f"สภ.ทดสอบ กก.{division}",
                "description": f"{MARKER} พฤติการณ์อุบัติเหตุ",
                "lat": "13.7563", "lng": "100.5018",
                "propDamageValue": int(division) * 1000,
            }
        }

    if kind == "mission":
        return {
            "formData": {
                **base,
                "startTime": "2026-07-26T10:00",
                "endTime": "2026-07-26T18:00",
                "missionDetails": f"{MARKER} ภารกิจทดสอบ กก.{division}",
                "location": f"ทล.{division} กม.{division}2",
            },
            "selectedUnits": [f"หน่วยฯทดสอบ กก.{division}"],
        }

    if kind == "royal-guard":
        return {
            "formData": {
                **base,
                "reportType": "prep",
                "commanders": f"พ.ต.อ. ผู้ควบคุม กก.{division}",
                "missionName": f"{MARKER} ถวายความปลอดภัย",
                "carNumbers": f"ทล.{station}05",
                "details": f"{MARKER} รายละเอียดภารกิจ",
                "targetCount": int(division),
            }
        }

    if kind == "fuel":
        return {
            "formData": {
                **base,
                "recordType": "เติมน้ำมัน",
                "actionDateTime": "2026-07-26T09:30",
                "actionPerson": f"ด.ต. ผู้เติม กก.{division}",
                "plateNumber": f"ทล.{station}06",
                "currentMileage": int(division) * 1000,
                "liters": int(division) * 10,
                "fuelType": "ดีเซล",
                "totalPrice": int(division) * 350,
                "receiptNumber": f"RC-{division}-001",
            }
        }

    if kind == "document":
        return {
            "formData": {
                **base,
                "subject": f"{MARKER} หนังสือทดสอบ กก.{division}",
                "docType": "หนังสือภายใน",
                "senderName": f"ฝอ.กก.{division}",
            }
        }

    return {
        "formData": {
            **base,
            "category": "ยาเสพติด",
            "arrestBy": "จับเอง",
            "arrestType": "ซึ่งหน้า",
            "warrantType": "ไม่ใช่หมายจับ",
            "actionDateTime": "2026-07-26T10:30",
            "suspectCount": 1,
            "location": f"ทล.{division} กม.{division}5",
            "lat": "13.7563",
            "lng": "100.5018",
            "items": f"ยาบ้า {division}00 เม็ด",
            "circumstances": f"{MARKER} พฤติการณ์ทดสอบ กก.{division}",
            "forwarding": f"ส่ง สภ.ทดสอบ กก.{division}",
            "warrantScope": "ไม่ใช่หมายจับ",
            "caseNumber": f"TEST-{division}-001",
        },
        "teamArray": [f"ด.ต. ชุดจับกุม กก.{division}"],
        "suspectArray": [
            {"name": f"นายทดสอบ กก.{division}", "idCard": f"1{division}00000000000",
             "nat": "ไทย", "age": "30", "address": f"ทดสอบ กก.{division}"}
        ],
        "chargeArray": ["มียาเสพติดให้โทษประเภท 1 ไว้ในครอบครองเพื่อจำหน่าย"],
    }


def section_1_auth(client) -> None:
    print("\nส่วนที่ 1  ระบบล็อกอินและการปฏิเสธที่ควรเกิด")

    from app.services import user_service

    users = user_service.get_all_users(force=True)
    record("auth", f"อ่านรายชื่อผู้ใช้จาก tb_Users ได้ ({len(users)} บัญชี)", bool(users))

    # ล็อกอินจริงด้วยบัญชีที่ยังเก็บรหัสผ่านแบบ plaintext ในชีต (ยังไม่ได้ hash)
    sample = [u for u in users.values() if u.get("password") and not u["password"].startswith("sha256$")][:6]
    for user in sample:
        res = client.post(
            "/api/login", json={"username": user["username"], "password": user["password"]}
        ).json()
        record("auth", f"ล็อกอิน {user['username']} ({user.get('role') or 'ไม่ระบุ role'}) สำเร็จและได้ token",
               res.get("status") == "success" and bool(res.get("user", {}).get("token")), str(res)[:140])

    probe = sample[0]["username"] if sample else "test6"
    bad = client.post("/api/login", json={"username": probe, "password": "definitely-wrong"}).json()
    record("auth", "รหัสผ่านผิดถูกปฏิเสธ", bad.get("status") == "error", str(bad)[:120])

    unknown = client.post("/api/login", json={"username": "no-such-user", "password": "x"}).json()
    record("auth", "บัญชีที่ไม่มีอยู่ถูกปฏิเสธ", unknown.get("status") == "error", str(unknown)[:120])

    station51 = next((u for u in users.values() if str(u.get("station")) == "51" and u.get("password")), None)
    if not station51:
        record("auth", "มีบัญชีสถานี 51 ไว้ทดสอบสิทธิ์", False, "ไม่พบใน tb_Users")
        return
    token = client.post(
        "/api/login", json={"username": station51["username"], "password": station51["password"]}
    ).json()["user"]["token"]
    body = payload_for("daily", "5", "51")

    record("auth", "ไม่ส่ง token ตอบ 401",
           client.post("/api/reports/daily", json=body).status_code == 401)
    record("auth", "token ปลอมตอบ 401",
           client.post("/api/reports/daily", json=body, headers={"x-token": "abc.def"}).status_code == 401)

    cross = {"formData": dict(body["formData"], stationId="21")}
    record("auth", "ส่งข้ามสถานีตอบ 403",
           client.post("/api/reports/daily", json=cross, headers={"x-token": token}).status_code == 403)

    no_station = {"formData": {k: v for k, v in body["formData"].items() if k != "stationId"}}
    record("auth", "ไม่มี stationId ตอบ 400",
           client.post("/api/reports/daily", json=no_station, headers={"x-token": token}).status_code == 400)

    bad_file = dict(body, files=[{"name": "x.exe", "type": "application/x-msdownload",
                                 "data": "data:application/x-msdownload;base64,aGVsbG8="}])
    record("auth", "ไฟล์แนบชนิดที่ไม่รองรับตอบ 400",
           client.post("/api/reports/daily", json=bad_file, headers={"x-token": token}).status_code == 400)

    legacy = dict(body, fileDataArray=[])
    record("auth", "ชื่อฟิลด์ที่ไม่รู้จักตอบ 422 แทนที่จะถูกทิ้งเงียบ",
           client.post("/api/reports/daily", json=legacy, headers={"x-token": token}).status_code == 422)

    missing = [e for e in UNIMPLEMENTED
               if client.post(f"/api/reports/{e}", json=body, headers={"x-token": token}).status_code != 404]
    record("scope", f"ฟอร์มที่ยังไม่รองรับตอบ 404 ครบทั้ง {len(UNIMPLEMENTED)} รายการ",
           not missing, f"ไม่ใช่ 404: {missing}")


def section_2_submit(client, divisions: List[str], kinds: List[str]) -> List[Dict[str, Any]]:
    print("\nส่วนที่ 2  ส่งรายงานจากทุก กก. ผ่าน API")
    submissions = []

    for division in divisions:
        station = f"{division}1"
        token = create_session_token({"username": f"verify_kk{division}", "role": "Unit_Staff", "station": station})

        for kind in kinds:
            res = client.post(f"/api/reports/{kind}", json=payload_for(kind, division, station),
                              headers={"x-token": token})
            ok = res.status_code == 200
            body = res.json() if ok else {}
            record("submit", f"กก.{division} สถานี {station} ส่ง {kind}", ok,
                   f"HTTP {res.status_code} {res.text[:160]}")
            if ok:
                submissions.append({
                    "division": division, "station": station, "kind": kind,
                    "recordId": body["recordId"], "savedTo": body["savedTo"],
                })

    return submissions


def section_3_readback(submissions: List[Dict[str, Any]], divisions: List[str]) -> Dict[str, Any]:
    print("\nส่วนที่ 3  อ่านกลับจากชีตของแต่ละ กก.")
    router = get_db_router()
    sheet_contents: Dict[str, Dict[str, List[List[str]]]] = {}
    # อ่านเฉพาะตารางที่ทดสอบจริงในรอบนี้ จะได้ไม่เปลือง read quota
    tables_in_use = sorted({REPORT_TABLES[item["kind"]] for item in submissions})

    for division in divisions:
        sheet_id = router[division]["OPS"]
        sheet_contents[division] = {}
        for table in tables_in_use:
            # ใช้ handle ที่ sheets_service แคชไว้ตอนเขียน จะได้ไม่เปลือง read quota ซ้ำ
            worksheet = with_retry(sheets_service.get_worksheet, sheet_id, table)
            sheet_contents[division][table] = with_retry(worksheet.get_all_values)
        print(f"  อ่านชีตของ กก.{division} แล้ว")

    for item in submissions:
        division, table, record_id = item["division"], REPORT_TABLES[item["kind"]], item["recordId"]
        rows = sheet_contents[division][table]
        header = rows[0] if rows else []
        row = next((r for r in rows[1:] if r and r[0] == record_id), None)

        if not record("flow", f"กก.{division} {item['kind']}: {record_id} อยู่ในชีตของ กก.{division}", row is not None):
            continue

        # ชีตที่ Apps Script สร้างไว้ก่อนใช้ป้ายหัวคอลัมน์คนละข้อความกับ schema ปัจจุบัน
        # (ดูคำอธิบายใน app/core/schema.py) สิ่งที่ต้องตรงจริง ๆ คือจำนวนคอลัมน์และ
        # 9 คอลัมน์มาตรฐาน เพราะทั้งระบบอ้างอิงด้วยตำแหน่ง ไม่ใช่ชื่อ
        expected = get_columns(table)
        record("flow", f"กก.{division} {item['kind']}: จำนวนคอลัมน์ตรง schema",
               len(header) == len(expected), f"{len(header)} vs {len(expected)}")
        record("flow", f"กก.{division} {item['kind']}: 9 คอลัมน์มาตรฐานตรง",
               header[:9] == expected[:9], f"{header[:9]}")

        legacy_labels = [(i + 1, h, e) for i, (h, e) in enumerate(zip(header, expected)) if h != e]
        if legacy_labels:
            detail = ", ".join(f"ช่อง {i}: ชีต {h!r} / schema {e!r}" for i, h, e in legacy_labels)
            print(f"  INFO  กก.{division} {item['kind']}: ป้ายหัวคอลัมน์ต่างจาก schema {len(legacy_labels)} ช่อง ({detail})")
        record("flow", f"กก.{division} {item['kind']}: Data_StationID = {item['station']}",
               row[7] == item["station"], f"ได้ {row[7]!r}")
        record("flow", f"กก.{division} {item['kind']}: Data_ActualDate = 2026-07-26",
               row[6] == "2026-07-26", f"ได้ {row[6]!r}")

        # ไม่ปนข้าม กก. — record นี้ต้องไม่โผล่ในชีตของ กก. อื่นเลย
        elsewhere = [d for d in divisions if d != division
                     and any(r and r[0] == record_id for r in sheet_contents[d][table][1:])]
        record("isolation", f"กก.{division} {item['kind']}: {record_id} ไม่ปนไปชีต กก. อื่น",
               not elsewhere, f"พบใน กก.{elsewhere}")

    daily = [s for s in submissions if s["kind"] == "daily"]
    for item in daily:
        rows = sheet_contents[item["division"]]["tb_DailyReport"]
        row = next((r for r in rows[1:] if r and r[0] == item["recordId"]), None)
        if row:
            phone = f"08{item['division']}1111111"[:10]
            record("flow", f"กก.{item['division']} daily: เบอร์โทรเก็บเลข 0 นำหน้าครบ",
                   row[11] == phone, f"ได้ {row[11]!r} คาดว่า {phone!r}")

    return sheet_contents


def section_4_attachments(client, divisions: List[str]) -> List[Dict[str, Any]]:
    """ส่งรายงานพร้อมไฟล์แนบ แล้วตรวจใน Drive จริงว่าไฟล์ขึ้นโฟลเดอร์ของ กก. นั้น"""
    print("\nส่วนที่ 4  ไฟล์แนบขึ้นโฟลเดอร์ Drive ของแต่ละ กก.")
    from app.services.storage_service import drive_service

    folders = get_division_folders()
    service = drive_service()
    created = []

    photo = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + MARKER.encode()).decode()

    for division in divisions:
        station = f"{division}1"
        if not record("attach", f"กก.{division} ตั้งค่าโฟลเดอร์ไฟล์แนบไว้แล้ว", bool(folders.get(division))):
            continue

        token = create_session_token({"username": f"verify_kk{division}", "role": "Unit_Staff", "station": station})
        body = payload_for("daily", division, station)
        body["files"] = [{"name": f"{MARKER}.png", "type": "image/png", "data": photo}]

        res = client.post("/api/reports/daily", json=body, headers={"x-token": token})
        if not record("attach", f"กก.{division} ส่งรายงานพร้อมไฟล์แนบ", res.status_code == 200,
                      f"HTTP {res.status_code} {res.text[:160]}"):
            continue

        payload = res.json()
        record("attach", f"กก.{division} ระบบยืนยันว่าเก็บไฟล์แล้ว", payload.get("attachmentsStored") is True, str(payload)[:160])
        record("attach", f"กก.{division} นับไฟล์ถูกต้อง", payload.get("attachmentCount") == 1, str(payload)[:120])

        folder_url = ""
        rows = with_retry(sheets_service.get_worksheet, get_db_router()[division]["OPS"], "tb_DailyReport")
        values = with_retry(rows.get_all_values)
        row = next((r for r in values[1:] if r and r[0] == payload["recordId"]), None)
        if row:
            folder_url = row[22]
        record("attach", f"กก.{division} คอลัมน์ไฟล์แนบเก็บลิงก์ Drive",
               folder_url.startswith("https://"), f"ได้ {folder_url!r}")

        folder_id = folder_url.rstrip("/").split("/")[-1].split("?")[0] if folder_url.startswith("https://") else ""
        if not folder_id:
            continue

        meta = service.files().get(fileId=folder_id, fields="id,name").execute()
        record("attach", f"กก.{division} โฟลเดอร์ตั้งชื่อ {payload['recordId']}_...",
               meta["name"].startswith(payload["recordId"]), meta["name"])

        # ถาม Drive จากฝั่งโฟลเดอร์แม่ เพราะ field parents คืน null เสมอภายใต้ scope ที่ใช้อยู่
        siblings = service.files().list(
            q=f"'{folders[division]}' in parents and trashed = false",
            fields="files(id,name)", pageSize=100,
        ).execute().get("files", [])
        record("attach", f"กก.{division} โฟลเดอร์อยู่ใต้ กองกำกับ {division}",
               any(f["id"] == folder_id for f in siblings), f"ไม่พบใน {len(siblings)} รายการ")

        children = service.files().list(q=f"'{folder_id}' in parents and trashed = false",
                                        fields="files(id,name)").execute().get("files", [])
        record("attach", f"กก.{division} มีไฟล์อยู่ในโฟลเดอร์ 1 ไฟล์",
               len(children) == 1 and children[0]["name"] == f"{MARKER}.png", str(children))

        created.append({"division": division, "kind": "daily", "recordId": payload["recordId"], "folderId": folder_id})

    return created


def cleanup_drive(created: List[Dict[str, Any]]) -> None:
    """ลบโฟลเดอร์ไฟล์แนบที่สคริปต์สร้างขึ้น"""
    if not created:
        return
    from app.services.storage_service import drive_service

    service = drive_service()
    for item in created:
        service.files().delete(fileId=item["folderId"]).execute()
    print(f"  ลบโฟลเดอร์ไฟล์แนบทดสอบ {len(created)} โฟลเดอร์")


def cleanup(submissions: List[Dict[str, Any]], sheet_contents: Dict[str, Any]) -> None:
    """ลบแถวที่สคริปต์นี้เขียนไว้ โดยใช้ข้อมูลที่อ่านมาแล้วในส่วนที่ 3 ไม่อ่านซ้ำ"""
    print("\nลบแถวทดสอบที่สคริปต์เขียนไว้")
    router = get_db_router()
    by_sheet: Dict[str, Dict[str, List[str]]] = {}
    for item in submissions:
        by_sheet.setdefault(item["division"], {}).setdefault(REPORT_TABLES[item["kind"]], []).append(item["recordId"])

    for division, tables in by_sheet.items():
        for table, record_ids in tables.items():
            worksheet = with_retry(sheets_service.get_worksheet, router[division]["OPS"], table)
            rows = sheet_contents.get(division, {}).get(table, [])

            # แถวที่เขียนหลังจากอ่านไว้ (เช่น รอบทดสอบไฟล์แนบ) จะยังไม่อยู่ในข้อมูลที่แคช
            if not all(any(r and r[0] == rid for r in rows) for rid in record_ids):
                rows = with_retry(worksheet.get_all_values)

            # ลบจากล่างขึ้นบน เลขแถวจะได้ไม่เลื่อน
            targets = [i for i, r in enumerate(rows, start=1) if i > 1 and r and r[0] in record_ids]
            for row_number in reversed(targets):
                with_retry(worksheet.delete_rows, row_number)
            print(f"  กก.{division} {table}: ลบ {len(targets)} แถว")


def main() -> int:
    parser = argparse.ArgumentParser(description="ตรวจการไหลของข้อมูลลงชีตรายกองกำกับ")
    parser.add_argument("--divisions", default="1,2,3,4,5,6,7,8", help="หมายเลข กก. คั่นด้วยจุลภาค")
    parser.add_argument(
        "--report-types",
        default="",
        help="จำกัดประเภทรายงานที่ทดสอบ คั่นด้วยจุลภาค (ค่าว่าง = ทุกประเภท)",
    )
    parser.add_argument("--cleanup", action="store_true", help="ลบแถวทดสอบออกเมื่อตรวจเสร็จ")
    args = parser.parse_args()

    if not sheets_service.is_configured():
        print(sheets_service.NOT_CONFIGURED_MESSAGE, file=sys.stderr)
        return 1

    router = get_db_router()
    divisions = [d.strip() for d in args.divisions.split(",") if d.strip()]
    unconfigured = [d for d in divisions if not (router.get(d) or {}).get("OPS")]
    if unconfigured:
        print(f"กก. {', '.join(unconfigured)} ยังไม่มีฐานข้อมูลใน DB_ROUTER_JSON", file=sys.stderr)
        print("รัน scripts/setup_database.py ก่อน", file=sys.stderr)
        return 1

    kinds = [k.strip() for k in args.report_types.split(",") if k.strip()] or list(REPORT_TABLES)
    unknown = [k for k in kinds if k not in REPORT_TABLES]
    if unknown:
        print(f"ไม่รู้จักประเภทรายงาน: {', '.join(unknown)}", file=sys.stderr)
        return 1

    from fastapi.testclient import TestClient
    from app.main import app

    print(f"ตรวจ กก. {', '.join(divisions)} x {len(kinds)} ประเภทรายงาน  (โหมด {sheets_service.auth_mode()})")

    with TestClient(app) as client:
        section_1_auth(client)
        submissions = section_2_submit(client, divisions, kinds)
        sheet_contents = section_3_readback(submissions, divisions)
        attachment_runs = section_4_attachments(client, divisions)

    if args.cleanup:
        if submissions or attachment_runs:
            cleanup(submissions + attachment_runs, sheet_contents)
        cleanup_drive(attachment_runs)

    print("\n" + "=" * 70)
    by_section: Dict[str, List[Dict[str, Any]]] = {}
    for item in results:
        by_section.setdefault(item["section"], []).append(item)

    titles = {
        "auth": "ล็อกอินและการปฏิเสธ", "scope": "ขอบเขตที่ยังไม่รองรับ",
        "submit": "การส่งรายงาน", "flow": "ข้อมูลลงชีตถูกต้อง", "isolation": "ไม่ปนข้าม กก.",
        "attach": "ไฟล์แนบขึ้น Drive",
    }
    for section, items in by_section.items():
        passed = sum(1 for i in items if i["ok"])
        print(f"{titles.get(section, section):28} {passed}/{len(items)}")

    failed = [i for i in results if not i["ok"]]
    print("=" * 70)
    print(f"รวม {len(results) - len(failed)}/{len(results)} ผ่าน")

    if failed:
        print("\nรายการที่ไม่ผ่าน:")
        for item in failed:
            print(f"  - {item['label']}  [{item['detail']}]")
        return 1

    print("ผ่านทั้งหมด ข้อมูลไหลลงชีตของแต่ละ กก. ถูกต้อง")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
