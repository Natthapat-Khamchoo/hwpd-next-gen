"""
รัน backend จริงทั้งตัว แต่แทนชั้น Google Sheets และ Drive ด้วยตัวจำลองในหน่วยความจำ

มีไว้ตรวจว่า **ข้อมูลที่กรอกจากหน้าเว็บไปลงตารางไหน คอลัมน์ไหน** โดยไม่ต้องมี
credentials ของ Google และไม่แตะข้อมูลจริงของหน่วย

ทุกอย่างที่อยู่เหนือชั้นข้อมูลเป็นของจริงทั้งหมด — เส้นทาง HTTP, การตรวจสิทธิ์,
การประกอบแถว, audit log, การตรวจคุณภาพสื่อ ตัวจำลองแทนที่แค่ตัวที่คุยกับ Google

    cd python_backend
    python scripts/dev_server_fake_sheets.py

ทุกการเขียนถูกบันทึกลง `scripts/_fake_sheet_writes.jsonl` และเรียกดูสด ๆ ได้ที่
    GET  http://localhost:8000/__fake/writes    ดูการเขียนทั้งหมดพร้อมชื่อคอลัมน์
    POST http://localhost:8000/__fake/reset     ล้างของเดิม

**ห้ามใช้ไฟล์นี้บนเซิร์ฟเวอร์จริง** ไม่มีการยืนยันตัวตนกับ Google เลยสักจุด
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SESSION_SECRET", "local-fake-sheets-only-not-for-production")
os.environ.setdefault(
    "DB_ROUTER_JSON",
    json.dumps({str(d): {"OPS": f"fake-sheet-div-{d}"} for d in range(1, 9)}),
)
os.environ.setdefault("ENABLE_API_DOCS", "true")
os.environ.setdefault("CORS_ORIGINS", "*")

WRITE_LOG = Path(__file__).with_name("_fake_sheet_writes.jsonl")

from app.core.schema import TABLE_COLUMNS, get_columns  # noqa: E402
from app.services import sheets_service, storage_service  # noqa: E402

# ---------------------------------------------------------------- ข้อมูลตั้งต้น

# บัญชีทดสอบ รหัสผ่านเป็น plaintext ตามที่ verify_password รองรับสำหรับข้อมูลเก่า
USERS: List[List[str]] = [
    get_columns("tb_Users"),
    ["test51", "1234", "ด.ต. ทดสอบ ระบบ", "51", "สามเงา", "Unit_Staff", "", "", "", "0810000001", "", "", "", ""],
    ["adm51", "1234", "ด.ต. สิบเวร ทดสอบ", "51", "สามเงา", "Station_Admin", "", "", "", "0810000002", "", "", "", ""],
    ["hq5", "1234", "พ.ต.ท. ฝอ. กก.5", "50", "ฝอ.กก.5", "Division_Admin", "", "", "", "0810000003", "", "", "", ""],
    ["cmd5", "1234", "พ.ต.อ. ผกก.5", "50", "ฝอ.กก.5", "Division_Commander", "", "", "", "0810000004", "", "", "", ""],
    ["hqadm", "1234", "พ.ต.อ. ฝอ.บก.ทล.", "00", "ฝอ.บก.ทล.", "HQ_Admin", "", "", "", "0810000005", "", "", "", ""],
    ["cmdhq", "1234", "พล.ต.ต. ผบก.ทล.", "00", "ฝอ.บก.ทล.", "Super_Commander", "", "", "", "0810000006", "", "", "", ""],
    ["pr01", "1234", "ร.ต.อ. ประชาสัมพันธ์ บก.ทล.", "00", "ฝ่าย ปชส.", "PR_Officer", "", "", "", "0810000007", "", "", "", ""],
]

CHARGES: List[List[str]] = [
    ["ชื่อข้อหา", "b", "c", "d", "isActive", "กลุ่ม พ.ร.บ."],
    ["ขับรถเร็วเกินกว่าที่กฎหมายกำหนด", "", "", "", "", ""],
    ["เมาแล้วขับ", "", "", "", "", ""],
    ["บรรทุกน้ำหนักเกินอัตราที่กฎหมายกำหนด", "", "", "", "", ""],
    ["ใช้ป้ายทะเบียนปลอม", "", "", "", "", ""],
    ["ขับรถขนส่งโดยไม่มีใบอนุญาตขับรถขนส่ง", "", "", "", "", ""],
    ["ยาเสพติดให้โทษประเภท 1", "", "", "", "", ""],
]

PR_KEYWORDS: List[List[str]] = [
    get_columns("tb_PR_Keywords"),
    ["ยาเสพติด", "คดี", "", "TRUE", "", "hqadm"],
    ["Scammer", "คดี", "", "TRUE", "", "hqadm"],
]

# ตาราง -> เนื้อหา (แถวแรกเป็นหัวคอลัมน์เสมอ)
SHEETS: Dict[str, List[List[Any]]] = {}


def reset_sheets() -> None:
    SHEETS.clear()
    for table in TABLE_COLUMNS:
        SHEETS[table] = [list(get_columns(table))]
    SHEETS["tb_Users"] = [list(r) for r in USERS]
    SHEETS["tb_Charges"] = [list(r) for r in CHARGES]
    SHEETS["tb_PR_Keywords"] = [list(r) for r in PR_KEYWORDS]
    SHEETS["tb_SeizedItemTypes"] = [["itemName", "category", "isActive"]]
    SHEETS["tb_ReportCatalog"] = [["reportKey", "title", "cadence"]]
    if WRITE_LOG.exists():
        WRITE_LOG.unlink()


reset_sheets()

# ---------------------------------------------------------------- ตัวจำลอง


# ทุกตารางที่ถูกอ่าน เรียงตามลำดับ ใช้ตอบว่า endpoint ไหนดึงข้อมูลจากชีตใด
# เก็บในหน่วยความจำอย่างเดียว เพราะเป็นข้อมูลระหว่างทดสอบรอบเดียว ไม่ต้องคงอยู่
READS: List[str] = []


def _record(action: str, table: str, rows: List[List[Any]]) -> None:
    """บันทึกการเขียนพร้อมจับคู่ค่ากับชื่อคอลัมน์ เพื่อให้อ่านออกว่าค่าไหนลงช่องไหน"""
    try:
        columns = get_columns(table)
    except KeyError:
        columns = []

    entries = []
    for row in rows:
        mapped = {}
        for index, value in enumerate(row):
            name = columns[index] if index < len(columns) else f"[คอลัมน์ที่ {index + 1}]"
            if value not in ("", None):
                mapped[name] = value
        entries.append(mapped)

    with WRITE_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "at": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "table": table,
            "rows": entries,
        }, ensure_ascii=False) + "\n")


def fake_read_table(spreadsheet_id: str, table_name: str) -> List[List[str]]:
    READS.append(table_name)
    if table_name not in SHEETS:
        raise sheets_service.SheetWriteError(f"ไม่พบตาราง {table_name}")
    return [[str(c) for c in row] for row in SHEETS[table_name]]


def fake_read_tables(spreadsheet_id: str, table_names: List[str]) -> Dict[str, List[List[str]]]:
    return {name: fake_read_table(spreadsheet_id, name) for name in table_names if name in SHEETS}


def fake_append_report_row(spreadsheet_id: str, table_name: str, row_data: List[Any]) -> Dict[str, Any]:
    columns = get_columns(table_name)
    if len(row_data) != len(columns):
        raise sheets_service.SheetWriteError(
            f"จำนวนข้อมูล ({len(row_data)}) ไม่ตรงกับหัวคอลัมน์ของ {table_name} ({len(columns)})"
        )
    SHEETS.setdefault(table_name, [list(columns)]).append(list(row_data))
    _record("append", table_name, [row_data])
    return {"spreadsheetId": spreadsheet_id, "tableName": table_name, "updatedRange": f"{table_name}!A{len(SHEETS[table_name])}"}


def fake_append_report_rows(spreadsheet_id: str, table_name: str, rows: List[List[Any]]) -> Dict[str, Any]:
    for row in rows:
        fake_append_report_row(spreadsheet_id, table_name, row)
    return {"spreadsheetId": spreadsheet_id, "tableName": table_name, "updatedRange": ""}


class FakeWorksheet:
    """รองรับเส้นทางที่แก้แถวเดิม (อนุมัติ ยกเลิก แก้ไข) ซึ่งเรียก batch_update"""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self.col_count = 60

    def _cell(self, ref: str):
        letters = "".join(c for c in ref if c.isalpha())
        digits = "".join(c for c in ref if c.isdigit())
        col = 0
        for ch in letters:
            col = col * 26 + (ord(ch) - ord("A") + 1)
        return col - 1, int(digits) - 1

    def _table(self) -> List[List[Any]]:
        """
        ตารางอ้างอิง (tb_Charges ฯลฯ) ไม่มีนิยามใน schema.py เพราะไม่ใช่ตารางรายงาน
        ถ้าไปเรียก get_columns ตรง ๆ จะ KeyError แล้ว 500 ทั้งที่แค่ไม่มีหัวคอลัมน์ให้เดา
        """
        if self.table_name in SHEETS:
            return SHEETS[self.table_name]
        try:
            header = list(get_columns(self.table_name))
        except KeyError:
            header = []
        return SHEETS.setdefault(self.table_name, [header])

    def batch_update(self, ranges, value_input_option=None):
        rows_touched = []
        for item in ranges:
            ref = item["range"].split("!")[-1]
            start = ref.split(":")[0]
            col, line = self._cell(start)
            table = self._table()
            while len(table) <= line:
                table.append([""] * len(table[0]))
            for offset, value in enumerate(item["values"][0]):
                while len(table[line]) <= col + offset:
                    table[line].append("")
                table[line][col + offset] = value
            rows_touched.append({"range": ref, "values": item["values"][0]})
        _record("update", self.table_name, [[json.dumps(rows_touched, ensure_ascii=False)]])
        return {}

    def append_row(self, row, value_input_option=None):
        return fake_append_report_row("fake", self.table_name, row)

    def append_rows(self, rows, value_input_option=None):
        return fake_append_report_rows("fake", self.table_name, rows)

    def row_values(self, index):
        return SHEETS.get(self.table_name, [[]])[index - 1]

    def add_cols(self, n):
        self.col_count += n

    def update(self, range_name=None, values=None, **kwargs):
        """
        เส้นทางที่ตารางอ้างอิงใช้เขียนแถว (reference_admin_service.upsert)

        ต้องเขียนจริงลง SHEETS ไม่ใช่คืน {} เฉย ๆ ไม่งั้นคำสั่งถัดไปที่ไปหาแถวนั้น
        จะไม่เจอ แล้วดูเหมือน backend พัง ทั้งที่เป็นตัวจำลองที่ไม่ครบ
        """
        if not range_name or not values:
            return {}
        ref = str(range_name).split("!")[-1]
        col, line = self._cell(ref.split(":")[0])
        table = self._table()
        while len(table) <= line:
            table.append([""] * len(table[0]))
        for row_offset, row in enumerate(values):
            target = table[line + row_offset]
            for offset, value in enumerate(row):
                while len(target) <= col + offset:
                    target.append("")
                target[col + offset] = value
        _record("update", self.table_name, [[json.dumps({"range": ref, "values": values}, ensure_ascii=False)]])
        return {}

    def freeze(self, rows=None):
        return {}


def fake_get_worksheet(spreadsheet_id: str, table_name: str, refresh: bool = False, ensure: bool = True):
    return FakeWorksheet(table_name)


def fake_store_attachments(files, station_id, record_id="", unit_name="", folder_id=""):
    """ไม่แตะ Drive จริง แต่ยังตรวจไฟล์ตามกติกาเดิม (จำนวน/ขนาด) แล้วคืนลิงก์ปลอม"""
    validated = storage_service.validate_attachments(files)
    if not validated:
        return {"stored": False, "count": 0, "folderUrl": "ไม่มีไฟล์แนบ", "links": []}
    _record("upload", "(Google Drive)", [[record_id, unit_name, f"{len(validated)} ไฟล์",
                                          ", ".join(str(f.get("name")) for f in validated)]])
    return {
        "stored": True,
        "count": len(validated),
        "folderUrl": f"https://drive.example/fake/{record_id}",
        "links": [{"name": f.get("name"), "url": f"https://drive.example/fake/{record_id}/{f.get('name')}"}
                  for f in validated],
    }


#: ไฟล์ที่ถูกเปิดสาธารณะอยู่ตอนนี้ {fileId: url} ใช้พิสูจน์ว่าถอนลิงก์แล้วมันหายจริง
PUBLIC_FILES: Dict[str, str] = {}


def fake_store_public_text(text, filename, station_id, folder_id=""):
    """ชิ้นงาน PR (FR-08) — ไม่แตะ Drive จริง แต่จำไว้ว่าตอนนี้อะไรเปิดสาธารณะอยู่บ้าง"""
    file_id = f"fake-{len(PUBLIC_FILES) + 1}-{filename}"
    url = f"https://drive.example/public/{file_id}"
    PUBLIC_FILES[file_id] = url
    _record("share", "(Google Drive)", [[filename, str(station_id), f"{len(text)} ตัวอักษร", url]])
    return {"stored": True, "fileId": file_id, "url": url, "warning": None}


def fake_revoke_public_link(file_id):
    if not PUBLIC_FILES.pop(str(file_id), None):
        return {"revoked": False, "warning": f"ไม่พบไฟล์ {file_id} ในรายการที่เปิดสาธารณะ"}
    _record("revoke", "(Google Drive)", [[str(file_id)]])
    return {"revoked": True, "removed": 1, "warning": None}


sheets_service.read_table = fake_read_table
sheets_service.read_tables = fake_read_tables
sheets_service.append_report_row = fake_append_report_row
sheets_service.append_report_rows = fake_append_report_rows
sheets_service.get_worksheet = fake_get_worksheet
sheets_service.is_configured = lambda: True
storage_service.store_attachments = fake_store_attachments
storage_service.store_public_text = fake_store_public_text
storage_service.revoke_public_link = fake_revoke_public_link

from app.main import app  # noqa: E402
from app.services import line_service, query_service  # noqa: E402

# ไม่ยิง LINE จริงระหว่างทดสอบ
line_service.push_line_message = lambda text, group_id=None: {"status": "success", "message": "(จำลอง) ไม่ได้ส่ง LINE"}
import app.main as main_module  # noqa: E402
main_module.push_line_message = line_service.push_line_message


@app.get("/__fake/writes")
def fake_writes():
    """ทุกการเขียนที่เกิดขึ้น พร้อมชื่อคอลัมน์ ใช้ตรวจว่าข้อมูลลงชีตไหน"""
    if not WRITE_LOG.exists():
        return {"count": 0, "writes": []}
    entries = [json.loads(line) for line in WRITE_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {"count": len(entries), "writes": entries}


@app.get("/__fake/reads")
def fake_reads():
    """ตารางที่ถูกอ่านไปแล้วทั้งหมด ใช้ตรวจว่า endpoint อ่านข้อมูลจากชีตไหน"""
    return {"count": len(READS), "reads": READS}


@app.post("/__fake/reads/reset")
def fake_reads_reset():
    READS.clear()
    query_service.invalidate_cache()
    return {"status": "success"}


@app.post("/__fake/reset")
def fake_reset():
    reset_sheets()
    query_service.invalidate_cache()
    return {"status": "success", "message": "ล้างข้อมูลจำลองแล้ว"}


if __name__ == "__main__":
    import uvicorn

    print("=" * 70)
    print(" backend จริง + ชั้นข้อมูลจำลอง (ไม่แตะ Google)")
    print(" บัญชีทดสอบ รหัสผ่าน 1234 ทุกบัญชี:")
    for row in USERS[1:]:
        print(f"   {row[0]:<8} {row[5]:<20} สถานี {row[3]}  {row[2]}")
    print(" ดูการเขียน: http://localhost:8000/__fake/writes")
    print("=" * 70)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
