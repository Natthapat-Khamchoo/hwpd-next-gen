"""
ออกรายงานตามแบบฟอร์มใน `tb_ReportCatalog` เป็นไฟล์ Excel

เริ่มจากแบบฟอร์มรอบรายวัน/รายสัปดาห์ที่ข้อมูลในระบบรองรับจริง แบบฟอร์มที่กรอง
ด้วยป้ายหมวด (ECIG, WEIGHT, GUN, CRIME5) ยังออกไม่ได้ ไม่ใช่เพราะเขียนโค้ดไม่ได้
แต่เพราะ `tb_Charges` ยังไม่มีข้อหากลุ่มนั้นและยังไม่มีใครติด `reportTags` เลยสักตัว
สร้างไปตอนนี้จะได้รายงานที่เป็นศูนย์ทุกช่อง ซึ่งอ่านแล้วเข้าใจผิดว่าไม่มีการจับกุม

ดูสถานะรายแบบฟอร์มได้จาก available_reports()
"""

import io
import logging
from typing import Any, Dict, List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.services import national_service

logger = logging.getLogger(__name__)


class ReportNotSupported(RuntimeError):
    """แบบฟอร์มนี้ยังออกไม่ได้"""


# reportKey -> รายละเอียดการออกรายงาน
# ต้องตรงกับ reportKey ใน tb_ReportCatalog
SUPPORTED = {
    "RPT_FRIDAY_STATS": {
        "title": "สถิติผลการปฏิบัติ (ส่งห้องขับเคลื่อน)",
        "cadence": "ทุกวันศุกร์",
    },
}

# ชื่อฟิลด์ใน national_summary -> หัวคอลัมน์บนรายงาน
METRICS = [
    ("arrestsCount", "จับกุมคดีอาญา"),
    ("v20Count", "คดีจราจร (ว.20)"),
    ("v43Count", "ว.43"),
    ("v42Count", "ว.42"),
    ("serviceCount", "บริการ"),
    ("volCount", "จิตอาสา"),
    ("royalCount", "รับเสด็จ"),
    ("missionCount", "ภารกิจ"),
    ("accCount", "อุบัติเหตุ"),
    ("deadCount", "เสียชีวิต"),
    ("injuredCount", "บาดเจ็บ"),
]

HEAD_FILL = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(bold=True, color="FFFFFF", size=11)
TOTAL_FILL = PatternFill("solid", fgColor="FFF2CC")
_thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)


def available_reports() -> List[Dict[str, Any]]:
    """แบบฟอร์มที่ออกได้ตอนนี้ พร้อมของที่ยังขาดสำหรับตัวที่ยังออกไม่ได้"""
    return [
        {"reportKey": key, "title": spec["title"], "cadence": spec["cadence"], "supported": True}
        for key, spec in SUPPORTED.items()
    ]


def build_workbook(report_key: str, start: str, end: str) -> bytes:
    """คืนไฟล์ Excel เป็น bytes ให้ endpoint ส่งต่อ"""
    spec = SUPPORTED.get(report_key)
    if not spec:
        raise ReportNotSupported(
            f"แบบฟอร์ม {report_key} ยังออกอัตโนมัติไม่ได้ "
            "แบบฟอร์มที่กรองด้วยป้ายหมวดต้องติด reportTags ใน tb_Charges ก่อน"
        )

    data = national_service.national_summary(start, end)
    totals = data.get("totals", {})
    by_division = sorted(data.get("byDivision", []), key=lambda r: str(r.get("div", "")))

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "ผลการปฏิบัติ"

    worksheet["A1"] = spec["title"]
    worksheet["A1"].font = Font(bold=True, size=14)
    worksheet["A2"] = f"ช่วงวันที่ {start} ถึง {end}   (รอบส่ง: {spec['cadence']})"
    worksheet["A2"].font = Font(size=10, color="595959")

    header_row = 4
    headers = ["กองกำกับการ"] + [label for _, label in METRICS]
    for index, label in enumerate(headers, start=1):
        cell = worksheet.cell(row=header_row, column=index, value=label)
        cell.fill, cell.font = HEAD_FILL, HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    worksheet.row_dimensions[header_row].height = 32
    worksheet.column_dimensions["A"].width = 18
    for index in range(2, len(headers) + 1):
        worksheet.column_dimensions[get_column_letter(index)].width = 14

    line = header_row
    for record in by_division:
        line += 1
        worksheet.cell(row=line, column=1, value=record.get("divName", "")).border = BORDER
        for offset, (field, _) in enumerate(METRICS, start=2):
            cell = worksheet.cell(row=line, column=offset, value=int(record.get(field, 0) or 0))
            cell.border = BORDER
            cell.alignment = Alignment(horizontal="center")

    line += 1
    cell = worksheet.cell(row=line, column=1, value="รวมทั้งประเทศ")
    cell.font, cell.fill, cell.border = Font(bold=True), TOTAL_FILL, BORDER
    for offset, (field, _) in enumerate(METRICS, start=2):
        cell = worksheet.cell(row=line, column=offset, value=int(totals.get(field, 0) or 0))
        cell.font, cell.fill, cell.border = Font(bold=True), TOTAL_FILL, BORDER
        cell.alignment = Alignment(horizontal="center")

    # ไม่มีแถวของ กก. ไหนเลยแปลว่ายังไม่มีใครรวมยอดในช่วงนั้น ไม่ใช่ว่ายอดเป็นศูนย์
    if not by_division:
        worksheet.cell(row=line + 2, column=1,
                       value="ไม่พบข้อมูลในช่วงวันที่นี้ — ตรวจว่าตัวตั้งเวลารวมยอดทำงานแล้วหรือยัง")

    worksheet.freeze_panes = f"A{header_row + 1}"

    stream = io.BytesIO()
    workbook.save(stream)
    logger.info("ออกรายงาน %s ช่วง %s ถึง %s (%d กก.)", report_key, start, end, len(by_division))
    return stream.getvalue()
