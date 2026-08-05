"""
ยิงทุก endpoint ที่ frontend เรียก เข้า harness (dev_server_fake_sheets) แล้วบันทึกว่า
ข้อมูลที่ส่งไปลงตารางไหนบ้าง

ใช้ payload รูปเดียวกับที่ฟอร์มจริงส่ง (formData + files/teamArray/... ตาม
ReportSubmissionRequest) เพื่อให้ผลที่ได้เป็นของเส้นทางเดียวกับที่ผู้ใช้กดจริง

    python scripts/sweep_endpoints.py            # ต้องเปิด harness ที่ :8000 ไว้ก่อน

ผลลัพธ์: scripts/_sweep_result.json
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://localhost:8000/api"
ROOT = pathlib.Path(__file__).resolve().parent
NOW = "2026-08-04T09:30"
TODAY = "2026-08-04"


def call(method: str, path: str, token: str = "", body: dict | None = None):
    # เข้ารหัสอักขระไทยใน query string ก่อน ไม่งั้น urllib โยน UnicodeEncodeError
    if "?" in path:
        head, _, query = path.partition("?")
        query = urllib.parse.urlencode(
            [(k, v) for k, v in urllib.parse.parse_qsl(query, keep_blank_values=True)]
        )
        path = f"{head}?{query}"
    url = f"{BASE}{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("x-token", token)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw[:300]}
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}


def login(username: str) -> str:
    status, body = call("POST", "/login", body={"username": username, "password": "1234"})
    if status != 200:
        raise SystemExit(f"ล็อกอิน {username} ไม่ผ่าน: {status} {body}")
    return body["user"]["token"]


def fake_writes() -> list[dict]:
    req = urllib.request.Request("http://localhost:8000/__fake/writes")
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode("utf-8"))["writes"]


def writes_since(mark: int) -> list[dict]:
    return fake_writes()[mark:]


def write_count() -> int:
    return len(fake_writes())


def reads_reset() -> None:
    """ล้างทั้งรายการอ่านและแคชแถว ไม่งั้น endpoint ที่สองอ่านจากแคชแล้วดูเหมือนไม่แตะชีตเลย"""
    urllib.request.urlopen(
        urllib.request.Request("http://localhost:8000/__fake/reads/reset", method="POST"), timeout=15
    ).read()


def reads_taken() -> list[str]:
    req = urllib.request.Request("http://localhost:8000/__fake/reads")
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode("utf-8"))["reads"]


ST = "51"          # กก.5 หน่วยบริการคลองขลุง
UNIT = "คลองขลุง"

# formData ร่วมของทุกฟอร์ม (frontend ใส่ให้เองจาก session)
BASE_FORM = {"stationId": ST, "unitId": UNIT, "actionBy": "test51", "reportDateTime": NOW}


def form(**extra) -> dict:
    return {**BASE_FORM, **extra}


# (ชื่อที่มนุษย์อ่าน, ฟอร์มที่เรียก, method, path, body)
REPORT_CASES = [
    (
        "รายงานประจำวัน (แท็บ 1)", "DailyReportForm", "/reports/daily",
        {
            "formData": form(
                unitName="หน่วยบริการฯ คลองขลุง", dutyOfficer="ด.ต. ทดสอบ ระบบ", dutyPhone="0810000001",
                carNumber="5115", driverName="ส.ต.อ. สมชาย ขับดี", driverPhone="0810000002",
                radioOpName="ส.ต.ท. วิทยุ ชัดเจน", radioOpPhone="0810000003",
                startTime="08:00", endTime="16:00", camTotal="4", camReady="3", camBroken="1",
            ),
            "files": [],
            "officers": [{"name": "จ.ส.ต. ร่วม ปฏิบัติ", "phone": "0810000004"}],
        },
    ),
    (
        "รายงานตั้งด่าน", "CheckpointForm", "/reports/checkpoint",
        {
            "formData": form(
                dutyOfficer="ด.ต. ทดสอบ ระบบ", totalPersonnel="4", carNumber="5115",
                location="หน้าหน่วยบริการสามเงา ทล.1 กม 571-572", locationOther="",
                lat="16.8765", lng="98.5432",
            ),
            "files": [],
        },
    ),
    (
        "รายงานการจับกุม", "ArrestForm", "/reports/arrest",
        {
            "formData": form(
                category="ยาเสพติด", arrestBy="ชุดปฏิบัติการ", arrestType="ซึ่งหน้า",
                warrantType="", actionDateTime=NOW, suspectCount="1",
                location="ทล.1 กม 570", lat="16.8000", lng="98.5000",
                items="ยาบ้า 200 เม็ด", circumstances="ตรวจค้นพบของกลาง",
                forwarding="ส่ง สภ.คลองขลุง", warrantScope="", caseNumber="อ.1/2569",
                caseMethod="ซึ่งหน้า", ecigType="", relatedUrl="",
                damageValue="0", turnoverValue="0",
            ),
            "files": [],
            "teamArray": ["ด.ต. ทดสอบ ระบบ", "ส.ต.อ. สมชาย ขับดี"],
            "suspectArray": [{"name": "นาย ก. ทดสอบ", "age": "30", "address": "ต.คลองขลุง"}],
            "chargeArray": ["มียาเสพติดให้โทษประเภท 1 ไว้ในครอบครองเพื่อจำหน่าย"],
            "seizedItems": [{"item": "ยาบ้า", "qty": "200", "unit": "เม็ด"}],
        },
    ),
    (
        "ผลการปฏิบัติประจำวัน (แท็บ 2)", "DailyReportForm", "/reports/daily-result",
        {
            "formData": form(
                unitName="หน่วยบริการฯ คลองขลุง",
                v43="5", service="3", v42="2", v20="4",
                v20Warrant="1", v20Flagrante="3",
                camTotal2="4", camReady2="3", camBroken2="1",
            ),
            "files": [],
            "charges": [{"charge": "ขับรถเร็วเกินกำหนด", "count": "3"}],
        },
    ),
    (
        "เวรประจำสถานี (แท็บ 3)", "DailyReportForm", "/reports/station-duty",
        {
            "formData": form(
                startTime="08:00", endTime="16:00",
                inspectorName="พ.ต.ท. ตรวจ เยี่ยม", inspectorPhone="0810000010",
                dutyOfficerName="ด.ต. ทดสอบ ระบบ", dutyOfficerPhone="0810000001",
                radioOpName="ส.ต.ท. วิทยุ ชัดเจน", radioOpPhone="0810000003",
            ),
        },
    ),
    (
        "สรุปยอดส่ง กก. (แท็บ 4)", "DailyReportForm", "/reports/daily-summary",
        {
            "formData": form(v43="5", service="3", v42="2", v20="4", chargesText="ขับรถเร็ว 3 ราย"),
        },
    ),
    (
        "ภารกิจอื่น ๆ (แท็บ 5)", "DailyReportForm", "/reports/other-duty",
        {
            "formData": form(
                dutyType="อื่น ๆ", dutyOtherText="อำนวยความสะดวกจราจร",
                carNumber="5115", actionDetails="จัดจราจรงานประเพณี",
                location="ตลาดคลองขลุง",
            ),
            "files": [],
            "officers": [{"name": "ด.ต. ทดสอบ ระบบ", "phone": "0810000001"}],
        },
    ),
    (
        "รายงานอุบัติเหตุ", "AccidentForm", "/reports/accident",
        {
            "formData": form(
                carNumber="5115", jointUnits="สภ.คลองขลุง, กู้ภัย",
                description="รถเก๋งชนท้ายรถบรรทุก", solutions="จัดจราจรและนำส่งโรงพยาบาล",
                govDamage="ไม่มี", propDamageValue="50000",
                lat="16.7000", lng="98.4000",
            ),
            "files": [],
        },
    ),
    (
        "แจ้งภารกิจ", "MissionForm", "/reports/mission",
        {
            "formData": form(
                startTime="08:00", endTime="12:00",
                missionDetails="ตรวจสอบเส้นทางถวายความปลอดภัย", location="ทล.1 กม 560-580",
            ),
            "files": [],
            "selectedUnits": ["คลองขลุง", "สามเงา"],
        },
    ),
    (
        "หมวดรายงานรับเสด็จ", "RoyalGuardForm", "/reports/royal-guard",
        {
            "formData": form(
                reportType="prep", missionName="ถวายความปลอดภัยเส้นทาง",
                commanders="พ.ต.อ. ผู้กำกับ ทดสอบ", carNumbers="5115, 5116",
                targetCount="20", details="ปล่อยแถวเวลา 06:00 น.",
            ),
            "files": [],
        },
    ),
    (
        "น้ำมัน / น้ำมันเครื่อง", "FuelForm", "/reports/fuel",
        {
            "formData": form(
                recordType="เติมน้ำมัน", actionDateTime=NOW, actionPerson="ด.ต. ทดสอบ ระบบ",
                plateNumber="5115", carType="รถยนต์ตรวจการณ์", currentMileage="120500",
                prevMileage="120000", distanceUsed="500",
                liters="40", fuelType="ดีเซล", totalPrice="1200", receiptNumber="RC-001",
            ),
            "files": [],
        },
    ),
    (
        "เซ็นเอกสารออนไลน์", "DocumentForm", "/reports/document",
        {
            "formData": form(subject="ขออนุมัติจัดซื้อ", docType="บันทึกข้อความ", senderName="ด.ต. ทดสอบ ระบบ"),
            "files": [],
        },
    ),
    (
        "รถบรรทุกน้ำหนักเกิน", "OverweightForm", "/reports/overweight",
        {
            "formData": form(
                inspectorName="ด.ต. ทดสอบ ระบบ", plateNumber="80-1234", plateProvince="ตาก",
                vehicleType="รถบรรทุก 10 ล้อ", axleCount="4",
                driverName="นาย ข. ทดสอบ", company="บริษัท ทดสอบ จำกัด", cargoType="หิน",
                location="ด่านชั่งน้ำหนักตาก", lat="16.9000", lng="98.6000",
                weighMethod="เครื่องชั่งเคลื่อนที่", actualWeight="32000", legalWeight="25000",
                action="เปรียบเทียบปรับ", charge="บรรทุกน้ำหนักเกินกว่าที่กฎหมายกำหนด",
                caseNumber="ป.5/2569", remark="ทดสอบระบบ",
            ),
            "files": [],
        },
    ),
    (
        "สรุปภารกิจ (ไม่เขียนตาราง)", "MissionViewForm", "/reports/mission-summary",
        {
            "formData": form(unitName=UNIT, startDate=TODAY, endDate=TODAY),
            "missions": [{"missionDetails": "ตรวจเส้นทาง", "location": "ทล.1"}],
        },
    ),
]


def main() -> int:
    results = []
    token = login("test51")
    adm = login("adm51")
    hq = login("hq5")
    cmd = login("cmd5")
    hqadm = login("hqadm")
    pr = login("pr01")

    print("== POST รายงาน ==")
    for label, comp, path, body in REPORT_CASES:
        mark = write_count()
        status, res = call("POST", path, token, body)
        new = writes_since(mark)
        tables = sorted({w["table"] for w in new})
        results.append({
            "kind": "report", "label": label, "component": comp, "path": path,
            "status": status, "ok": status == 200 and res.get("status") == "success",
            "tables": tables,
            "columns": {w["table"]: list(w["rows"][0].keys()) for w in new if w["rows"]},
            "message": res.get("message") or res.get("detail"),
        })
        flag = "OK " if results[-1]["ok"] else "FAIL"
        print(f"  [{flag}] {label:38s} {status} -> {', '.join(tables) or '(ไม่เขียนตาราง)'}")
        if not results[-1]["ok"]:
            print(f"        {res}")

    print("\n== POST อื่น ๆ ==")
    other_posts = [
        ("ส่งข่าว ปชส.", "PrForm", "/pr/news", token, {
            "formData": {
                "stationId": ST, "unitId": UNIT, "actionBy": "test51", "reportDateTime": NOW,
                "title": "ตำรวจทางหลวงจับกุมยาเสพติด", "category": "จับกุม", "source": "internal",
                "body": "รายละเอียดข่าวทดสอบระบบ", "location": "ทล.1 กม 570",
                "mediaMeta": [{"name": "a.jpg", "type": "image/jpeg", "width": 1920, "height": 1080}],
            },
            "files": [],
        }),
        ("คีย์เวิร์ด ปชส.", "PrPanel", "/pr/keywords", hqadm, {"keyword": "ทดสอบคีย์เวิร์ด"}),
        ("โควตาน้ำมัน", "FuelPanel", "/hq/fuel/quota", hq, {
            "stationId": "50", "monthYear": "2026-08",
            "quotas": [{"stationId": "51", "baht": 5000, "oilLiters": 40}],
        }),
        ("สถานภาพกำลังพล", "ManpowerPanel", "/hq/manpower/status", hq, {
            "username": "test51", "helpStationId": "52",
            "startDate": TODAY, "endDate": TODAY, "note": "ทดสอบระบบ",
        }),
        ("จัดหมวดของกลาง", "EvidencePanel", "/hq/evidence", hq, {
            "stationId": "50", "recordId": "__ARREST_ID__",
            "items": [{"category": "ยาเสพติด", "name": "ยาบ้า", "qty": "200", "unit": "เม็ด"}],
        }),
        ("บันทึกนำขบวน", "EscortPanel", "/hq/escort", hq, {
            "stationId": "50", "escortType": "นำขบวนบุคคลสำคัญ",
            "startDateTime": NOW, "endDateTime": "2026-08-04T12:00",
            "details": "ทล.1 กม 560-580",
        }),
        ("สั่งการ ผกก.", "CommanderDashboard", "/commander/order", cmd, {
            "target": "51", "message": "ทดสอบสั่งการ", "commanderName": "พ.ต.อ. ทดสอบ",
        }),
        ("แก้แถวตารางอ้างอิง", "ReferenceTableEditor", "/admin/reference/charges", hqadm, {
            "values": {"ชื่อข้อหา": "ทดสอบข้อหาใหม่"},
        }),
        ("เปิด/ปิดแถวอ้างอิง", "ReferenceTableEditor", "/admin/reference/charges/active", hqadm, {
            "key": "ทดสอบข้อหาใหม่", "active": False,
        }),
        ("แก้โปรไฟล์ผู้ใช้", "UserDirectory", "/admin/users/update", hqadm, {
            "username": "test51", "fullName": "ด.ต. ทดสอบ ระบบ", "phone": "0810000009",
        }),
        ("วิเคราะห์ผลปฏิบัติ", "AnalysisPanel", "/hq/analysis", hq, {
            "stationId": "50", "start": TODAY, "end": TODAY,
            "mode": "daily_charges", "categories": ["ขับรถเร็วเกินกำหนด"],
        }),
        ("เทียบสองช่วงเวลา", "AnalysisPanel", "/hq/comparison", hq, {
            "stationId": "50", "mode": "daily_charges", "category": "ขับรถเร็วเกินกำหนด",
            "ranges": [{"start": TODAY, "end": TODAY}, {"start": TODAY, "end": TODAY}],
        }),
    ]
    # ใช้รหัสจับกุมจริงที่เพิ่งสร้าง ให้ /hq/evidence มีคดีให้แก้จริง
    arrest_id = next(
        (w["rows"][0].get("Sys_RecordID") for w in fake_writes()
         if w["table"] == "tb_Arrests" and w["rows"]),
        "",
    )
    for label, comp, path, tok, body in other_posts:
        if body.get("recordId") == "__ARREST_ID__":
            body = {**body, "recordId": arrest_id}
        mark = write_count()
        status, res = call("POST", path, tok, body)
        new = writes_since(mark)
        tables = sorted({w["table"] for w in new})
        ok = status in (200, 202) and res.get("status") != "error"
        results.append({
            "kind": "post", "label": label, "component": comp, "path": path,
            "status": status, "ok": ok, "tables": tables,
            "columns": {w["table"]: list(w["rows"][0].keys()) for w in new if w["rows"]},
            "message": res.get("message") or res.get("detail"),
        })
        print(f"  [{'OK ' if ok else 'FAIL'}] {label:38s} {status} -> {', '.join(tables) or '(ไม่เขียนตาราง)'}")
        if not ok:
            print(f"        {res}")

    print("\n== GET (อ่านอย่างเดียว) ==")
    gets = [
        ("dropdown หน่วย", "useStationData", f"/dropdowns/units?station={ST}", token),
        ("dropdown ผู้ปฏิบัติ", "useStationData", f"/dropdowns/users?station={ST}", token),
        ("dropdown เบอร์โทร", "useStationData", f"/dropdowns/user-phones?station={ST}", token),
        ("dropdown ข้อหา", "ChargeSelect", "/dropdowns/charges", token),
        ("ข้อหาแบ่งกลุ่ม", "ChargeSelect/AnalysisPanel", "/dropdowns/charges-grouped", token),
        ("รายการรออนุมัติของฉัน", "MyHistoryForm", "/my-pending?username=test51", token),
        ("รายการรออนุมัติของหน่วย", "StationAdminDashboard", f"/station-pending?station={ST}", adm),
        ("ภารกิจ", "MissionViewForm", f"/missions?station={ST}&start={TODAY}&end={TODAY}", token),
        ("สรุปยอดวัน", "DailyReportForm", f"/daily-summary?station={ST}&start={TODAY}&end={TODAY}", token),
        ("สรุป กก.", "HqDashboard", f"/division-summary?station=50&start={TODAY}&end={TODAY}", hq),
        ("สรุปทั้งประเทศ", "HqAdminDashboard", f"/national-summary?start={TODAY}&end={TODAY}", hqadm),
        ("สรุปทั้งประเทศ (รวมที่เก็บแล้ว)", "SuperCommanderDashboard", f"/national-summary?start={TODAY}&end={TODAY}&includeArchived=true", hqadm),
        ("จุดบนแผนที่", "MapPanel", f"/map/points?station=50&start={TODAY}&end={TODAY}", hq),
        ("ค้นหาระดับ กก.", "SearchPanel", f"/search/division?station=50&keyword=ทดสอบ&start={TODAY}&end={TODAY}", hq),
        ("ค้นหาระดับประเทศ", "SearchPanel", f"/search/national?keyword=ทดสอบ&start={TODAY}&end={TODAY}", hqadm),
        ("ตารางอ้างอิง", "ReferenceTableEditor", "/admin/reference/charges", hqadm),
        ("รายชื่อผู้ใช้", "UserDirectory", "/admin/users", hqadm),
        ("สถานะการรวมยอด", "HqAdminDashboard", "/admin/aggregate-status", hqadm),
        ("รายงานที่ export ได้", "ReportExportPanel", "/reports/catalog/exportable", hqadm),
        ("สุขภาพฐานข้อมูล", "SuperCommanderDashboard", "/health/database", hqadm),
        ("น้ำมัน (ฝอ.)", "FuelPanel", "/hq/fuel?station=50", hq),
        ("กำลังพล (ฝอ.)", "ManpowerPanel", "/hq/manpower?station=50", hq),
        ("ของกลาง (ฝอ.)", "EvidencePanel", "/hq/evidence?station=50", hq),
        ("นำขบวน (ฝอ.)", "EscortPanel", "/hq/escort?station=50", hq),
        ("รายละเอียดรายวัน", "HqDashboard", f"/hq/daily-detail?station=50&date={TODAY}", hq),
        ("ภาพรวม ผกก.", "CommanderDashboard", "/commander/overview?station=50", cmd),
        ("รายชื่อ กก.", "CommanderDashboard", "/commander/divisions", cmd),
        ("ปฏิทิน ผกก.", "CommanderDashboard", "/commander/calendar?station=50", cmd),
        ("สรุป ผกก.", "CommanderDashboard", "/commander/summary?station=50", cmd),
        ("หมวดวิเคราะห์", "AnalysisPanel", "/hq/analysis/categories", hq),
        ("PR ข่าว (อ่าน)", "PrPanel", "/pr/news?station=50", hq),
        ("PR คีย์เวิร์ด (อ่าน)", "PrPanel/PrForm", "/pr/keywords", hq),
    ]
    for label, comp, path, tok in gets:
        reads_reset()
        status, res = call("GET", path, tok)
        # 200 ที่มี status:"error" คือคำขอไม่ผ่าน เช่นลืมส่งคำค้น ต้องไม่นับว่าผ่าน
        ok = status == 200 and (not isinstance(res, dict) or res.get("status") != "error")
        tables = sorted(set(reads_taken()))
        results.append({
            "kind": "get", "label": label, "component": comp, "path": path,
            "status": status, "ok": ok, "tables": tables, "columns": {},
            "message": None if ok else (res.get("detail") or res.get("error") or res.get("message")),
        })
        print(f"  [{'OK ' if ok else 'FAIL'}] {label:38s} {status} <- {', '.join(tables) or '(ไม่อ่านชีต)'}")
        if not ok:
            print(f"        {res}")

    print("\n== แก้ไข / อนุมัติ / ยกเลิก ==")
    # หา record ที่เพิ่งสร้างมาทดสอบเส้นทางแก้ไข
    status, pend = call("GET", "/my-pending?username=test51", token)
    target = None
    if status == 200:
        items = pend if isinstance(pend, list) else (pend.get("data") or [])
        # เอารายการรถบรรทุกน้ำหนักเกิน เพราะมีคอลัมน์ "หมายเหตุ" ให้แก้จริง
        target = next((i for i in items if i.get("sheetName") == "tb_OverweightTrucks"), items[0] if items else None)
    if target:
        sheet = target["sheetName"]
        rid = target["recordId"]
        # หารายการที่สองไว้ทดสอบเส้นทางยกเลิก จะได้ไม่ชนกับที่เพิ่งอนุมัติไป
        second = next((i for i in items if i["recordId"] != rid), None)
        for label, comp, method, path, tok, body in [
            ("ดูรายละเอียดรายการ", "RecordDetailModal", "GET", f"/records/detail?sheetName={sheet}&recordId={rid}", token, None),
            ("แก้ไขรายการ", "RecordDetailModal", "POST", "/records/update", token,
             {"sheetName": sheet, "recordId": rid, "updates": {"หมายเหตุ": "แก้ไขจากการทดสอบ"}}),
            ("อนุมัติรายการ", "StationAdminDashboard", "POST", "/records/approve", adm,
             {"sheetName": sheet, "recordId": rid}),
            ("ยกเลิกรายการ (soft delete)", "MyHistoryForm", "POST", "/records/cancel", token,
             {"sheetName": second["sheetName"], "recordId": second["recordId"]} if second else {}),
        ]:
            if not body and method == "POST":
                continue
            mark = write_count()
            status, res = call(method, path, tok, body)
            new = writes_since(mark)
            ok = status == 200
            results.append({
                "kind": "record", "label": label, "component": comp, "path": path,
                "status": status, "ok": ok,
                "tables": sorted({w["table"] for w in new}),
                "columns": {}, "message": None if ok else (res.get("detail") or res.get("error")),
            })
            print(f"  [{'OK ' if ok else 'FAIL'}] {label:38s} {status}")
            if not ok:
                print(f"        {res}")
    else:
        print("  (ไม่มีรายการรออนุมัติให้ทดสอบ)")

    print("\n== ชิ้นงาน PR และลิงก์สาธารณะ (FR-07/08/10) ==")
    # ข่าวที่ POST /pr/news สร้างไว้ตอนต้น ต้องอนุมัติก่อนถึงจะแชร์ได้ตามกติกาของ FR-08
    news_id = next(
        (w["rows"][0].get("Sys_RecordID") for w in fake_writes()
         if w["table"] == "tb_PR_News" and w["rows"]),
        "",
    )
    if news_id:
        pr_cases = [
            ("เทมเพลตชิ้นงาน PR", "PrPanel", "GET", "/pr/templates", adm, None),
            ("ประกอบชิ้นงาน (ก่อนอนุมัติ)", "PrPanel", "POST", "/pr/news/compose", adm,
             {"recordId": news_id, "template": "press"}),
            ("แชร์ก่อนอนุมัติต้องถูกปฏิเสธ", "PrPanel", "POST", "/pr/news/share", adm,
             {"recordId": news_id, "template": "press"}, 409),
            ("อนุมัติข่าว", "PrPanel", "POST", "/pr/news/decide", adm,
             {"recordId": news_id, "approve": True}),
            ("สร้างลิงก์สาธารณะ", "PrPanel", "POST", "/pr/news/share", adm,
             {"recordId": news_id, "template": "facebook"}),
            ("ถอนลิงก์สาธารณะ", "PrPanel", "POST", "/pr/news/share/revoke", adm,
             {"recordId": news_id}),
            # PrPanel ถูกใช้สองที่ HqDashboard ส่ง station=50 (ฝอ.กก.)
            # ส่วน StationAdminDashboard ส่งสถานีของตัวเอง จึงต้องผ่านทั้งสองแบบ
            ("รายงานข่าวค้าง (ฝอ.กก.)", "PrPanel", "GET", "/pr/report/pending?station=50", hq, None),
            ("รายงานข่าวค้าง (สิบเวรสถานี)", "PrPanel", "GET", f"/pr/report/pending?station={ST}", adm, None),
            ("สิบเวรดูข้ามไป กก. ไม่ได้", "PrPanel", "GET", "/pr/report/pending?station=50", adm, None, 403),
            ("ผู้ปฏิบัติเปิดรายงานค้างไม่ได้", "PrPanel", "GET", "/pr/report/pending", token, None, 403),
            # ฝ่าย ปชส. ส่วนกลาง — ทำงาน PR ได้เต็มวงจร แต่แตะอย่างอื่นไม่ได้เลย
            ("ฝ่าย PR ดูรายชื่อ กก.", "PrCenterDashboard", "GET", "/pr/divisions", pr, None),
            ("ฝ่าย PR ดูรายงานค้าง", "PrCenterDashboard", "GET", "/pr/report/pending?station=50", pr, None),
            ("ฝ่าย PR ประกอบชิ้นงาน", "PrCenterDashboard", "POST", "/pr/news/compose", pr,
             {"recordId": news_id, "station": ST, "template": "press"}),
            ("ฝ่าย PR เปิดยอดทั้งประเทศไม่ได้", "-", "GET", "/national-summary?station=00", pr, None, 403),
            ("ฝ่าย PR เปิดกำลังพลไม่ได้", "-", "GET", "/hq/manpower?station=50", pr, None, 403),
            ("ฝ่าย PR เปิดทะเบียนผู้ใช้ไม่ได้", "-", "GET", "/admin/users", pr, None, 403),
        ]
        for case in pr_cases:
            label, comp, method, path, tok, body = case[:6]
            expect = case[6] if len(case) > 6 else 200
            mark = write_count()
            status, res = call(method, path, tok, body)
            new = writes_since(mark)
            ok = status == expect and (status != 200 or not isinstance(res, dict) or res.get("status") != "error")
            results.append({
                "kind": "pr", "label": label, "component": comp, "path": path,
                "status": status, "ok": ok, "tables": sorted({w["table"] for w in new}),
                "columns": {}, "message": None if ok else (res.get("detail") or res.get("message")),
            })
            print(f"  [{'OK ' if ok else 'FAIL'}] {label:38s} {status} (คาด {expect})")
            if not ok:
                print(f"        {res}")
    else:
        print("  (ไม่มีข่าว ปชส. ให้ทดสอบ)")

    fail = [r for r in results if not r["ok"]]
    print(f"\nรวม {len(results)} กรณี ผ่าน {len(results) - len(fail)} ไม่ผ่าน {len(fail)}")
    for r in fail:
        print(f"  ไม่ผ่าน: {r['label']} ({r['path']}) {r['status']} {r['message']}")

    (ROOT / "_sweep_result.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
