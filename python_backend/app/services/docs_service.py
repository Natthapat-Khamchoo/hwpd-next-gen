"""
HWPD Next Gen - Auto-generated arrest paperwork.

คัดลอกแม่แบบ Google Docs แล้วแทนที่ตัวยึด `<<FIELD>>` ด้วยข้อมูลจากฟอร์ม
เทียบเท่า generateAutoArrestDocs ใน รหัส.js

ได้เอกสารสองชนิด:
  - บันทึกจับกุม 1 ฉบับ รวมผู้ต้องหาทุกคน
  - บันทึก ม.22, 23 คนละฉบับต่อผู้ต้องหาหนึ่งคน

ใช้ credentials ชุดเดียวกับที่เขียนชีต — scope `drive` ครอบคลุม Docs API อยู่แล้ว
จึงไม่ต้องขอ consent ใหม่
"""

import logging
import os
from typing import Any, Dict, List

from app.services import sheets_service

logger = logging.getLogger(__name__)

NOT_CONFIGURED_MESSAGE = (
    "ยังไม่ได้ตั้งค่าแม่แบบเอกสารจับกุม ระบบจึงสร้างเอกสารไม่ได้ "
    "ตั้ง AUTO_ARREST_DOC_ID, AUTO_ARREST_M22_ID และ AUTO_ARREST_FOLDER_ID "
    "(ดูค่าที่ Apps Script เดิมใช้ได้จาก Script Properties)"
)


class TemplateNotConfigured(RuntimeError):
    """ยังไม่ได้ตั้งค่า ID ของแม่แบบหรือโฟลเดอร์ปลายทาง"""


class DocumentError(RuntimeError):
    """สร้างเอกสารไม่สำเร็จ"""


def template_settings() -> Dict[str, str]:
    return {
        "main": os.getenv("AUTO_ARREST_DOC_ID", "").strip(),
        "m22": os.getenv("AUTO_ARREST_M22_ID", "").strip(),
        "folder": os.getenv("AUTO_ARREST_FOLDER_ID", "").strip(),
    }


def is_configured() -> bool:
    return all(template_settings().values())


def _services():
    """คืน (drive, docs) จาก credentials ชุดเดียวกับ sheets_service"""
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise TemplateNotConfigured(
            "ยังไม่ได้ติดตั้ง google-api-python-client (pip install -r requirements.txt)"
        ) from exc

    credentials = sheets_service.get_credentials()
    return (
        build("drive", "v3", credentials=credentials, cache_discovery=False),
        build("docs", "v1", credentials=credentials, cache_discovery=False),
    )


def _copy(drive, template_id: str, name: str, folder_id: str) -> str:
    copied = drive.files().copy(
        fileId=template_id,
        body={"name": name, "parents": [folder_id]},
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return copied["id"]


def _replace(docs, document_id: str, values: Dict[str, Any]) -> None:
    """
    แทนที่ตัวยึดทั้งหมดในคำขอเดียว

    ค่าว่างก็ยังต้องส่งไปแทนที่ ไม่งั้นตัวยึด `<<FIELD>>` จะค้างอยู่ในเอกสารที่พิมพ์ออกมา
    """
    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": f"<<{key}>>", "matchCase": True},
                "replaceText": str(value or ""),
            }
        }
        for key, value in values.items()
    ]
    docs.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()


def _download_url(document_id: str) -> str:
    return f"https://docs.google.com/document/d/{document_id}/export?format=docx"


def _discard(drive, document_id: str) -> None:
    """
    ลบสำเนาที่แทนที่ข้อความไม่สำเร็จ

    ถ้าปล่อยไว้ เจ้าหน้าที่จะเจอเอกสารที่ตัวยึด `<<OFFENSE>>` ยังค้างอยู่ปนกับ
    ฉบับที่ใช้ได้จริงในโฟลเดอร์เดียวกัน แล้วอาจหยิบไปพิมพ์
    """
    try:
        drive.files().delete(fileId=document_id, supportsAllDrives=True).execute()
    except Exception:
        logger.warning("ลบสำเนาที่สร้างค้างไว้ไม่สำเร็จ (%s) ต้องลบเองใน Drive", document_id)


def _explain(error: Exception) -> str:
    """แปลข้อผิดพลาดที่เจอบ่อยให้เป็นสิ่งที่ผู้ดูแลระบบลงมือแก้ได้"""
    text = str(error)
    if "SERVICE_DISABLED" in text and "docs.googleapis.com" in text:
        return (
            "ยังไม่ได้เปิดใช้งาน Google Docs API ในโปรเจกต์ Google Cloud ที่ออก OAuth ให้ระบบนี้ "
            "เปิดที่ https://console.cloud.google.com/apis/library/docs.googleapis.com "
            "แล้วรอสักครู่ให้มีผลก่อนลองใหม่"
        )
    if "insufficientPermissions" in text or "insufficientFilePermissions" in text:
        return "บัญชีที่ให้ consent ไว้ไม่มีสิทธิ์แก้ไขแม่แบบหรือโฟลเดอร์ปลายทาง ตรวจการแชร์ใน Drive"
    if "notFound" in text or "404" in text:
        return "ไม่พบแม่แบบหรือโฟลเดอร์ตาม ID ที่ตั้งไว้ ตรวจ AUTO_ARREST_DOC_ID / AUTO_ARREST_M22_ID / AUTO_ARREST_FOLDER_ID"
    return text


def _officer_fields(form: Dict[str, Any]) -> Dict[str, str]:
    """
    ฟอร์มส่งชื่อฟิลด์สั้น (respOfficer) แต่แม่แบบฝั่ง Apps Script อ่านชื่อยาว
    (respOfficerName) รับทั้งสองแบบ ไม่งั้นช่องเจ้าหน้าที่ในเอกสารจะว่างเปล่า
    """
    def pick(*names: str) -> str:
        for name in names:
            value = str(form.get(name, "")).strip()
            if value:
                return value
        return ""

    return {
        "RESPONSIBLE_OFFICER_NAME": pick("respOfficerName", "respOfficer"),
        "RESPONSIBLE_OFFICER_PHONE": pick("respOfficerPhone", "respPhone"),
        "NOTIFYING_OFFICER_NAME": pick("notifyOfficerName", "notifyOfficer"),
        "NOTIFYING_OFFICER_PHONE": pick("notifyOfficerPhone", "notifyPhone"),
    }


def generate_arrest_documents(
    form_data: Dict[str, Any],
    suspects: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """
    สร้างเอกสารทั้งชุด คืนรายการ [{'name', 'url'}] ตามลำดับที่หน้าเว็บแสดงปุ่มดาวน์โหลด
    ขว้าง TemplateNotConfigured / DocumentError เมื่อทำไม่สำเร็จ
    """
    settings = template_settings()
    if not all(settings.values()):
        raise TemplateNotConfigured(NOT_CONFIGURED_MESSAGE)
    if not sheets_service.is_configured():
        raise TemplateNotConfigured(sheets_service.NOT_CONFIGURED_MESSAGE)

    from app.services.report_service import format_thai_datetime

    record_date = format_thai_datetime(form_data.get("recordDate", ""))
    arrest_date = format_thai_datetime(form_data.get("arrestDate", ""))
    officers = _officer_fields(form_data)
    people = [s for s in (suspects or []) if isinstance(s, dict) and str(s.get("name", "")).strip()]

    try:
        drive, docs = _services()
    except TemplateNotConfigured:
        raise
    except Exception as exc:
        raise DocumentError(f"เชื่อมต่อ Google Docs ไม่ได้: {exc}") from exc

    links: List[Dict[str, str]] = []
    day = str(form_data.get("arrestDate", "")).split("T")[0] or "ไม่ระบุวันที่"
    in_progress: str = ""

    def build(template: str, name: str, values: Dict[str, Any], label: str) -> None:
        nonlocal in_progress
        in_progress = _copy(drive, template, name, settings["folder"])
        _replace(docs, in_progress, values)
        links.append({"name": label, "url": _download_url(in_progress)})
        in_progress = ""

    try:
        build(settings["main"], f"บันทึกจับกุม_{day}", {
            "RECORD_DATE": record_date,
            "ARREST_DATE": arrest_date,
            "ALL_SUSPECTS": form_data.get("allSuspectsText", ""),
            "OFFENSE": form_data.get("offense", ""),
            "ARREST_LOCATION": form_data.get("arrestLocation", ""),
            "DETENTION_LOCATION": form_data.get("detentionLocation", ""),
            "CIRCUMSTANCES": form_data.get("circumstances", ""),
            # Thai placeholders for กก.7 template
            "สถานที่ทำบันทึก": form_data.get("detentionLocation") or form_data.get("recordLocation", ""),
            "วันที่เป็นพศ": record_date,
            "เวลาจับกุม": form_data.get("arrestTime") or (str(form_data.get("arrestDate", "")).split("T")[1] if "T" in str(form_data.get("arrestDate", "")) else ""),
            "สถานที่จับกุม": form_data.get("arrestLocation", ""),
            "ผู้บังคับบัญชา": form_data.get("commanders", "ผู้บังคับบัญชาตามลำดับชั้น"),
            "สถานี": form_data.get("stationName", form_data.get("stationId", "")),
            "รวมชุดจับกุม": form_data.get("arrestTeam", form_data.get("respOfficer", "")),
            "คำนำหน้าชื่อผู้ต้องหา": form_data.get("suspectTitle", ""),
            "ชื่อ-สกุล ผู้ต้องหา": form_data.get("allSuspectsText", ""),
            "รายการของกลาง": form_data.get("items", ""),
            "ข้อหาสุทธิ": form_data.get("offense", ""),
            "พฤติการณ์สุทธิ": form_data.get("circumstances", ""),
            "พฤติการณ์โดยย่อ": form_data.get("briefCircumstances", form_data.get("circumstances", "")),
            "คำให้การผู้ต้องหา": form_data.get("suspectPlea", "ให้การรับสารภาพตลอดข้อกล่าวหา"),
            "ผู้ควบคุมตัว": form_data.get("respOfficer", ""),
            "เบอร์โทรผู้ควบคุมตัว": form_data.get("respPhone", ""),
            "ส่งผู้ต้องหาให้กับพนักงานสอบสวนที่ใด": form_data.get("forwarding", ""),
            "รายงานอัยการจังหวัดใด": form_data.get("prosecutorOffice", ""),
            **officers,
        }, "บันทึกจับกุม (รวมทุกคน)")

        for person in people:
            name = str(person.get("name", "")).strip()
            title = person.get("title", "") or ("นาย" if not name.startswith("นาย") and not name.startswith("นาง") else "")
            build(settings["m22"], f"บันทึก_ม22_23_{name}", {
                "RECORD_DATE": record_date,
                "ARREST_DATE": arrest_date,
                "SUSPECT_NAME": name,
                "SUSPECT_IDCARD": person.get("idCard", ""),
                "SUSPECT_NAT": person.get("nat", ""),
                "SUSPECT_AGE": person.get("age", ""),
                "SUSPECT_ADDRESS": person.get("address", ""),
                "SUSPECT_PHONE": person.get("phone", ""),
                "BRIEF_CIRCUM": form_data.get("briefCircumstances", ""),
                "DETENTION_LOCATION": form_data.get("detentionLocation", ""),
                "ARREST_LOCATION": form_data.get("arrestLocation", ""),
                # Thai placeholders for กก.7 template
                "คำนำหน้าชื่อผู้ต้องหา": title,
                "ชื่อ-สกุล ผู้ต้องหา": name,
                "อายุผู้ต้องหา": person.get("age", ""),
                "เลขประจำตัวประชาชนผู้ต้องหา": person.get("idCard", ""),
                "ที่อยู่ตามบัตรประชาชนผู้ต้องหา": person.get("address", ""),
                "วันเกิดผู้ต้องหา": person.get("dob", "-"),
                "ตำหนิรูปพรรณผู้ถูกจับ": person.get("distinguishingMarks", "ไม่ปรากฏตำหนิเด่นชัด"),
                "วันที่เป็นพศ": arrest_date,
                "สถานที่จับกุม": form_data.get("arrestLocation", ""),
                "ข้อหาสุทธิ": form_data.get("offense", ""),
                "รายการของกลาง": form_data.get("items", ""),
                "พฤติการณ์โดยย่อ": form_data.get("briefCircumstances", form_data.get("circumstances", "")),
                "ผู้ควบคุมตัว": form_data.get("respOfficer", ""),
                "เบอร์โทรผู้ควบคุมตัว": form_data.get("respPhone", ""),
                "ส่งผู้ต้องหาให้กับพนักงานสอบสวนที่ใด": form_data.get("forwarding", ""),
                "รายงานอัยการจังหวัดใด": form_data.get("prosecutorOffice", ""),
                **officers,
            }, f"ม.22,23 ของ {name}")
    except Exception as exc:
        # สำเนาที่ค้างอยู่ยังมีตัวยึด <<...>> ครบ ใช้ไม่ได้ ทิ้งไปเลย
        # ส่วนฉบับที่เสร็จก่อนหน้าเก็บไว้ ผู้ใช้จะได้ไม่ต้องเริ่มใหม่ทั้งชุด
        if in_progress:
            _discard(drive, in_progress)
        made = ", ".join(link["name"] for link in links) or "ยังไม่ได้สร้างเอกสารใด"
        raise DocumentError(f"{_explain(exc)} (เอกสารที่สร้างเสร็จแล้ว: {made})") from exc

    logger.info("สร้างเอกสารจับกุมแล้ว %d ฉบับ (ผู้ต้องหา %d คน)", len(links), len(people))
    return links
