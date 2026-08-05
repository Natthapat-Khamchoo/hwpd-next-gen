"""
HWPD Next Gen - Python FastAPI Backend Entry Point
Exposes REST Endpoints matching the Google Apps Script RPC contracts.
"""

import base64
import logging
import os
from contextlib import asynccontextmanager

import hmac
import threading
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict
from typing import Dict, Any, List, Optional

from app.core.config import (
    MASTER_SHEET_ID,
    check_station_match,
    get_db_router,
    get_session_secret,
    get_station_config,
    get_division_stations,
    get_station_data,
    get_target_db_id,
)
from app.core.schema import TABLE_COLUMNS, get_columns
from app.core.sanitization import sanitize_form_data
from app.core.security import (
    hash_password,
    verify_password,
    create_session_token,
    verify_session_token,
)
from app.services.report_service import (
    build_mission_summary,
    generate_record_id,
    prepare_hq_summary,
    prepare_accident_report,
    prepare_arrest_report,
    prepare_checkpoint_report,
    prepare_daily_report,
    prepare_daily_result,
    prepare_document_record,
    prepare_overweight_report,
    prepare_fuel_record,
    prepare_mission_report,
    prepare_other_duty,
    prepare_royal_guard_report,
    prepare_station_duty,
)
from app.services import (
    charge_group_service,
    pr_service,
    audit_service,
    docs_service,
    hq_service,
    map_service,
    national_service,
    query_service,
    reference_admin_service,
    reference_service,
    report_cache_service,
    report_export_service,
    search_service,
    sheets_service,
    storage_service,
    user_service,
)
from app.services import docx_service  # noqa: E402  แยกบรรทัดเพราะเป็นทางเลือกที่อาจไม่มีไลบรารี
from app.services.docs_service import DocumentError, TemplateNotConfigured
from app.services.query_service import RecordNotFound
from app.services.reference_service import ReferenceDataUnavailable
from app.services.sheets_service import SheetNotConfigured, SheetWriteError, append_report_row
from app.services.user_service import UserDirectoryUnavailable
from app.services.storage_service import AttachmentError, parse_data_url, store_attachments
from app.services.line_service import push_line_message

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    ล้มตั้งแต่ตอนบูตถ้า SESSION_SECRET ยังไม่ได้ตั้งค่า ดีกว่าปล่อยให้ระบบขึ้นแล้ว
    ไปพังตอนเจ้าหน้าที่กดล็อกอิน
    """
    get_session_secret()
    yield


# หน้าเอกสาร API ปิดไว้เป็นค่าเริ่มต้น เปิดด้วย ENABLE_API_DOCS=true เมื่อต้องการ
#
# /docs /redoc /openapi.json ของ FastAPI เปิดให้ทุกคนโดยไม่ต้องล็อกอิน และแจง
# endpoint ทั้งหมดพร้อมชื่อฟิลด์ทุกตัว ไม่ใช่ช่องโหว่ตรง ๆ เพราะทุกเส้นยังต้องมี token
# แต่เป็นการแจกแผนผังระบบให้คนนอกฟรี ซึ่งไม่ควรสำหรับระบบราชการ
#
# ตั้งค่าเริ่มต้นเป็นปิด ไม่ใช่ "ปิดเมื่อเป็น production" เพราะแบบหลังต้องอาศัยว่ามีคน
# ตั้งตัวแปรบอกว่านี่คือ production ไว้ถูก ลืมเมื่อไหร่ก็เปิดโล่งเมื่อนั้น ทางนี้ลืมแล้ว
# ผลคือปิด ซึ่งเป็นด้านที่ปลอดภัยกว่า
_docs_enabled = os.getenv("ENABLE_API_DOCS", "").strip().lower() in {"1", "true", "yes"}

app = FastAPI(
    title="HWPD Next Gen API",
    description="Python Backend API for Highway Police Division (บก.ทล.)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)


# CORS — the frontend (Vercel) calls this API from a different origin.
# Set CORS_ORIGINS on the host to a comma-separated allowlist; defaults to "*"
# (safe here because auth uses a bearer-style token header, not cookies).
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_trail_middleware(request: Request, call_next):
    """
    เปิดบัฟเฟอร์ audit ตอนเริ่ม request แล้วเขียนทีเดียวตอนจบ

    เขียนเฉพาะเมื่อ response เป็น 2xx เพราะ audit ของ action ที่ล้มเหลว (403, 400,
    502) คือร่องรอยของสิ่งที่ไม่เคยเกิดขึ้นจริง ถ้าเก็บไว้ ตอนสอบย้อนหลังจะแยกไม่ออก
    ว่ารายการไหนสำเร็จ ส่วน endpoint ที่อยากเก็บร่องรอยการพยายามที่ถูกปฏิเสธไว้ด้วย
    ต้องเรียก audit_service.flush() เองก่อนขว้าง HTTPException
    """
    audit_service.begin()
    try:
        response = await call_next(request)
    except Exception:
        audit_service.discard()
        raise

    if 200 <= response.status_code < 300:
        audit_service.flush()
    else:
        audit_service.discard()

    return response


@app.exception_handler(ValueError)
def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    """
    get_target_db_id ขว้าง ValueError เมื่อ กก. นั้นยังไม่ได้ตั้งค่าฐานข้อมูล
    ซึ่งเป็นเรื่องคอนฟิก ไม่ใช่ระบบพัง จึงตอบ 400 พร้อมข้อความไทยแทน 500
    """
    return JSONResponse(status_code=400, content={"status": "error", "message": str(exc)})


try:
    from gspread.exceptions import GSpreadException

    @app.exception_handler(GSpreadException)
    def handle_gspread_error(request: Request, exc: Exception) -> JSONResponse:
        """
        gspread โยน error ของตัวเอง (`SpreadsheetNotFound`, `APIError`) ที่ไม่ได้สืบทอด
        `SheetWriteError` ของโปรเจกต์ ทุก endpoint จึงจับไม่ติดแล้วกลายเป็น 500
        "Internal Server Error" เปล่า ๆ ที่ไม่บอกอะไรกับคนหน้างานเลย

        รอบก่อนแก้ปัญหานี้ทีละ endpoint ที่ `/api/health/database` แต่ต้นเหตุเป็นของทั้งระบบ
        — สเปรดชีตที่ยังไม่ได้แชร์ให้บัญชีบริการ หรือรหัสชีตผิด ล้มแบบเดียวกันทุกเส้นทาง
        ตอบ 502 เพราะเป็นความล้มเหลวของบริการต้นทาง ไม่ใช่คำขอของผู้ใช้ผิด
        """
        logger.error("gspread ล้มที่ %s: %s: %s", request.url.path, type(exc).__name__, exc)
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "message": f"ติดต่อฐานข้อมูล Google Sheets ไม่สำเร็จ ({type(exc).__name__}) "
                           "กรุณาลองใหม่ ถ้ายังไม่ได้ให้แจ้งผู้ดูแลระบบ",
            },
        )
except ImportError:  # pragma: no cover — เครื่องที่ยังไม่ได้ติดตั้ง gspread
    logger.warning("ไม่พบ gspread จึงไม่ได้ลงทะเบียนตัวจัดการ error ของมัน")


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    """ชื่อฟิลด์ต้องตรงกับที่ api.ts ส่งมา (oldPassword / newPassword ไม่ใช่ snake_case)"""

    model_config = ConfigDict(extra="forbid")

    username: str
    oldPassword: str
    newPassword: str


class RecordActionRequest(BaseModel):
    """สำหรับอนุมัติ/ยกเลิก — stationId ไม่รับจากหน้าเว็บ ใช้ของ session เสมอ"""

    model_config = ConfigDict(extra="forbid")

    sheetName: str
    recordId: str
    username: Optional[str] = None


MIN_PASSWORD_LENGTH = 8

# บทบาทที่อนุมัติ/ตีกลับรายงานของคนอื่นได้ ตรงกับ requireSession_ ใน approveItem ของ JS
APPROVER_ROLES = {"สิบเวร", "Station_Admin", "Division_Admin", "Division_Commander", "HQ_Admin", "Super_Commander"}

# บทบาทที่เห็นภาพรวมทั้ง กก. ได้ ตรงกับหน้าที่ index.html เดิมเปิดให้เข้า hq/commander dashboard
DIVISION_VIEW_ROLES = {"Division_Admin", "Division_Commander", "HQ_Admin", "Super_Commander"}

# ภาพรวมทั้งประเทศเป็นของระดับ บก. เท่านั้น ฝอ.กก. ใช้ /api/division-summary
NATIONAL_VIEW_ROLES = {"HQ_Admin", "Super_Commander"}

# บทบาทที่ "อ่าน" สถิติของ กก. อื่นได้ (requirement ข้อ 1)
#
# ผู้กำกับการอยู่ในชุดนี้เพื่อดูสถิติเทียบกับกองอื่น แต่ **ไม่ได้แปลว่าสั่งการข้ามกองได้**
# ทุกเส้นทางที่เขียนข้อมูลยังใช้ authorized_station / authorized_station_id ซึ่งยึด
# check_station_match ตามเดิม ชุดนี้จึงถูกใช้เฉพาะกับ endpoint ที่อ่านอย่างเดียว
#
# ฝอ.กก. ไม่อยู่ในชุดนี้ เพราะ requirement ระบุถึงผู้กำกับการอย่างเดียว
CROSS_DIVISION_VIEW_ROLES = {"Division_Commander", "HQ_Admin", "Super_Commander"}

# บทบาทที่ทำได้เฉพาะงานประชาสัมพันธ์ ไม่ใช่แอดมินของระบบที่บังเอิญดูงาน PR ด้วย
PR_ONLY_ROLES = {"PR_Officer"}

# เส้นทางที่บัญชี PR_ONLY_ROLES เรียกได้ นอกจากนี้ตอบ 403 ทั้งหมด
#
# ต้องกันที่นี่ ไม่ใช่แค่ซ่อนเมนู — ฝ่าย PR อยู่สถานี "00" ระดับ บก. ซึ่ง
# check_station_match("00", สถานีอะไรก็ได้) คืน True เสมอ ด่านขอบเขตสถานีที่ endpoint
# ฝั่งอ่านส่วนใหญ่ใช้จึงไม่กันบัญชีนี้เลยสักเส้น ถ้าไม่มีรายการนี้ คนที่เปิด DevTools เป็น
# จะอ่านรายงานจับกุม ยอดน้ำมัน และกำลังพลของทั้งแปดกองได้ ทั้งที่หน้าจอไม่มีปุ่มให้กด
#
# เขียนเป็น allowlist ไม่ใช่ denylist เพราะ endpoint ใหม่ที่จะเพิ่มในอนาคตต้องถูกปิด
# ไว้ก่อนโดยปริยาย ไม่ใช่เปิดแล้วรอให้มีคนนึกได้ว่าต้องไปเพิ่มในรายการที่ห้าม
PR_ONLY_ALLOWED_PREFIXES = (
    "/api/pr/",
    "/api/logout",
    "/api/change-password",
)

# เรียกได้แบบตรงตัวเท่านั้น ไม่นับ path ที่ขึ้นต้นด้วยค่าเหล่านี้
PR_ONLY_ALLOWED_EXACT = frozenset({"/api/login", "/api/health", "/api/dropdowns/units"})

# กันไม่ให้รอบรวมยอดสองรอบเขียนทับกันเองเมื่อถูก trigger ซ้อน
_aggregate_lock = threading.Lock()

# แคชรายงานก็เขียนชีตเดียวกัน จึงต้องกันซ้อนแยกอีกตัว
_report_cache_lock = threading.Lock()

# ผลรอบรวมยอดล่าสุด ให้ /api/admin/aggregate-status อ่านไปตรวจว่ารอบที่แล้วผ่านจริงไหม
_aggregate_status_lock = threading.Lock()
_last_aggregate: Dict[str, Any] = {
    "status": "never",
    "start": "",
    "end": "",
    "detail": "ยังไม่เคยรวมยอดนับตั้งแต่ service เริ่มทำงาน",
    "result": {},
    "finishedAt": "",
}


class ReportSubmissionRequest(BaseModel):
    """
    สัญญาข้อมูลระหว่างฟอร์มกับ API — ชื่อฟิลด์ต้องตรงกับที่ api.ts ส่งมาเป๊ะ ๆ
    extra="forbid" ทำให้ field ที่สะกดผิดตอบ 422 แทนที่จะถูกทิ้งเงียบ ๆ
    """

    model_config = ConfigDict(extra="forbid")

    formData: Dict[str, Any]
    files: Optional[List[Dict[str, Any]]] = None
    teamArray: Optional[List[str]] = None
    suspectArray: Optional[List[Dict[str, Any]]] = None
    chargeArray: Optional[List[str]] = None
    seizedItems: Optional[List[Dict[str, Any]]] = None
    selectedUnits: Optional[List[str]] = None
    charges: Optional[List[Any]] = None
    officers: Optional[List[Any]] = None
    missions: Optional[List[Any]] = None


def _enforce_pr_only(session: Dict[str, Any], path: str) -> None:
    """
    บัญชีของฝ่ายประชาสัมพันธ์เรียกได้เฉพาะเส้นทางในรายการที่อนุญาต

    ด่านนี้อยู่ที่ `current_session` เพราะเป็นจุดเดียวที่ทุก endpoint ซึ่งต้องล็อกอิน
    วิ่งผ่านแน่นอน การไปเติมเงื่อนไขทีละ endpoint แปลว่า endpoint ที่เพิ่มวันหลัง
    จะเปิดให้บัญชีนี้โดยปริยาย ซึ่งเป็นค่าตั้งต้นที่ผิดด้านสำหรับบัญชีที่ตั้งใจจำกัด
    """
    if str(session.get("r") or "") not in PR_ONLY_ROLES:
        return
    if path in PR_ONLY_ALLOWED_EXACT or path.startswith(PR_ONLY_ALLOWED_PREFIXES):
        return
    raise HTTPException(
        status_code=403,
        detail="บัญชีฝ่ายประชาสัมพันธ์ใช้ได้เฉพาะงานประชาสัมพันธ์เท่านั้น",
    )


def current_session(request: Request, x_token: Optional[str] = Header(None)) -> Dict[str, Any]:
    """ตรวจ Session Token ของทุก endpoint ที่เขียนข้อมูล"""
    session = verify_session_token(x_token or "")
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Session หมดอายุหรือไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่",
        )
    _enforce_pr_only(session, request.url.path)
    return session


def authorized_station(form_data: Dict[str, Any], session: Dict[str, Any]) -> str:
    """
    บังคับว่า stationId ที่ส่งมาต้องอยู่ในขอบเขตที่ session นั้นมองเห็นได้
    กันไม่ให้ผู้ใช้สถานีหนึ่งยิงรายงานเข้าฐานข้อมูลของอีกสถานี
    """
    station_id = str(form_data.get("stationId") or "").strip()
    if not station_id:
        raise HTTPException(status_code=400, detail="ไม่พบรหัสสถานี (stationId) ในข้อมูลที่ส่งมา")

    if not check_station_match(str(session.get("s") or ""), station_id):
        raise HTTPException(status_code=403, detail=f"ไม่มีสิทธิ์บันทึกข้อมูลของสถานี {station_id}")

    return station_id


def authorized_station_id(station_id: Optional[str], session: Dict[str, Any]) -> str:
    """
    เหมือน authorized_station แต่รับรหัสสถานีจาก query string ของ endpoint ฝั่งอ่าน
    ไม่ระบุมา = ใช้สถานีของ session นั้นเอง ซึ่งเป็นกรณีปกติของทุกฟอร์ม
    """
    own_station = str(session.get("s") or "").strip()
    requested = str(station_id or "").strip() or own_station

    if not requested:
        raise HTTPException(status_code=400, detail="ไม่พบรหัสสถานี (station)")

    if not check_station_match(own_station, requested):
        raise HTTPException(status_code=403, detail=f"ไม่มีสิทธิ์ดูข้อมูลของสถานี {requested}")

    return requested


def authorized_station_for_stats(station_id: Optional[str], session: Dict[str, Any]) -> str:
    """
    เหมือน `authorized_station_id` แต่ปล่อยให้ระดับผู้กำกับการขึ้นไปอ่านสถิติข้าม กก. ได้

    **ใช้กับ endpoint ที่อ่านอย่างเดียวเท่านั้น ห้ามเอาไปใช้กับเส้นทางที่เขียนข้อมูล**
    requirement ข้อ 1 ให้ ผกก. ดูสถิติของ กก. อื่นได้แต่สั่งการไม่ได้ ถ้าเอาตัวนี้ไปคุม
    เส้นทางเขียนด้วย ผกก. จะบันทึก/อนุมัติ/สั่งการข้ามกองได้ทันทีซึ่งตรงข้ามกับที่ขอ
    เส้นทางเขียนทุกเส้นยังใช้ `authorized_station` / `authorized_station_id` ตามเดิม

    ฝอ.กก. (`Division_Admin`) ไม่ได้อยู่ในชุดนี้ เพราะ requirement พูดถึงผู้กำกับการ
    อย่างเดียว การเปิดให้ฝ่ายอำนวยการเห็นข้ามกองด้วยเป็นการขยายสิทธิ์ที่ไม่มีใครขอ
    """
    own_station = str(session.get("s") or "").strip()
    requested = str(station_id or "").strip() or own_station

    if not requested:
        raise HTTPException(status_code=400, detail="ไม่พบรหัสสถานี (station)")

    if str(session.get("r") or "") in CROSS_DIVISION_VIEW_ROLES:
        return requested

    if not check_station_match(own_station, requested):
        raise HTTPException(status_code=403, detail=f"ไม่มีสิทธิ์ดูข้อมูลของสถานี {requested}")

    return requested


def is_viewing_other_division(station_id: str, session: Dict[str, Any]) -> bool:
    """
    กำลังเปิดดูข้อมูลของ กก. อื่นอยู่หรือเปล่า ใช้ติดธง readOnly กลับไปให้หน้าเว็บ

    หน้าเว็บซ่อนปุ่มสั่งการเองอยู่แล้ว แต่การซ่อนปุ่มไม่ใช่การจำกัดสิทธิ์ ตัวจริงที่กัน
    คือ 403 ฝั่ง API ธงนี้มีไว้ให้ผู้ใช้รู้ตัวว่ากำลังดูของหน่วยอื่น ไม่ใช่กลไกความปลอดภัย
    """
    own = str(session.get("s") or "").strip()
    return bool(own) and bool(station_id) and own[0] != str(station_id)[0]


def prepare_attachments(
    files: Optional[List[Dict[str, Any]]],
    station_id: str,
    record_id: str,
    unit_name: str,
) -> Dict[str, Any]:
    """
    ตรวจและอัปโหลดไฟล์แนบก่อนบันทึกรายงาน แปลง AttachmentError เป็น 400 พร้อมเหตุผลภาษาไทย
    ทำก่อนเขียนชีตเพราะลิงก์โฟลเดอร์ต้องถูกเขียนลงคอลัมน์ไฟล์แนบและข้อความ LINE
    """
    try:
        return store_attachments(files, station_id, record_id=record_id, unit_name=unit_name)
    except AttachmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def persist_report(prepared: Dict[str, Any]) -> Dict[str, Any]:
    """
    เขียนแถวลง Google Sheet ของ กก. นั้น ต้องสำเร็จก่อนถึงจะถือว่าบันทึกรายงานแล้ว
    ถ้าเขียนไม่ได้ให้ตอบ error ไม่ใช่ปล่อยผ่านแล้วส่ง LINE ราวกับบันทึกสำเร็จ
    """
    try:
        result = append_report_row(prepared["targetDbId"], prepared["tableName"], prepared["rowData"])
        # ล้างแคชตารางนี้ทันที ไม่งั้นคนที่เพิ่งส่งจะไม่เห็นรายการตัวเองในคิวอีกครึ่งนาที
        # แล้วกดส่งซ้ำ กลายเป็นรายงานซ้ำในฐานข้อมูล
        query_service.invalidate_cache(prepared["targetDbId"], prepared["tableName"])
        return result
    except SheetNotConfigured as exc:
        logger.error("บันทึกลง Sheet ไม่ได้เพราะยังไม่ได้ตั้งค่า: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SheetWriteError as exc:
        logger.error("บันทึกลง Sheet ไม่สำเร็จ: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def submission_response(
    message: str,
    prepared: Dict[str, Any],
    attachments: Dict[str, Any],
    written: Dict[str, Any],
) -> Dict[str, Any]:
    """รวมผลลัพธ์ให้ฟอร์ม โดยต่อท้ายคำเตือนเรื่องไฟล์แนบถ้ามี"""
    warning = attachments.get("warning")
    return {
        "status": "success",
        "message": warning or message,
        "recordId": prepared["recordId"],
        "attachmentsStored": attachments.get("stored", True),
        "attachmentCount": attachments.get("count", 0),
        "savedTo": {
            "spreadsheetId": written.get("spreadsheetId", ""),
            "tableName": written.get("tableName", ""),
            "range": written.get("updatedRange", ""),
        },
    }


def submit(
    prepared: Dict[str, Any],
    attachments: Dict[str, Any],
    message: str,
) -> Dict[str, Any]:
    """ลำดับเดียวกันทุกรายงาน: เขียนลงชีตให้สำเร็จก่อน แล้วค่อยแจ้ง LINE"""
    written = persist_report(prepared)

    if prepared.get("lineGroupId"):
        line_result = push_line_message(prepared["lineMessage"], prepared["lineGroupId"])
        if line_result.get("status") == "error":
            # ข้อมูลบันทึกแล้ว การแจ้ง LINE ล้มเหลวไม่ควรทำให้ทั้งรายงานกลายเป็น error
            logger.warning("บันทึก %s แล้วแต่ส่ง LINE ไม่สำเร็จ: %s", prepared["recordId"], line_result.get("message"))

    return submission_response(message, prepared, attachments, written)


@app.get("/")
def read_root():
    return {"system": "HWPD Next Gen Python API", "status": "online", "version": "1.0.0"}


@app.post("/api/login")
def login(req: LoginRequest):
    """
    ตรวจสอบบัญชีกับแท็บ tb_Users ในชีตกลาง รองรับทั้งรหัสผ่านแบบ SHA-256 และ
    Plaintext เดิม (Lazy Migration) แล้วคืน Session Token ที่เซ็นด้วย HMAC
    """
    username = req.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="กรุณาระบุ Username")

    try:
        user = user_service.get_user(username)
    except UserDirectoryUnavailable as exc:
        # แยกให้ชัดว่าเป็นปัญหาระบบ ไม่ใช่ผู้ใช้กรอกรหัสผิด
        logger.error("อ่านรายชื่อผู้ใช้ไม่ได้: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="ระบบเข้าถึงรายชื่อผู้ใช้ไม่ได้ในขณะนี้ กรุณาลองใหม่หรือแจ้งผู้ดูแลระบบ",
        ) from exc

    if not user or not verify_password(username, req.password, user.get("password", "")):
        return {"status": "error", "message": "Username หรือ Password ไม่ถูกต้อง"}

    if not str(user.get("station") or "").strip():
        return {"status": "error", "message": "บัญชีนี้ยังไม่ได้กำหนดสถานี กรุณาแจ้งผู้ดูแลระบบ"}

    token = create_session_token(
        {"username": user["username"], "role": user["role"], "station": user["station"]}
    )
    return {
        "status": "success",
        "user": {
            "username": user["username"],
            "fullName": user.get("fullName", ""),
            "station": user["station"],
            "unit": user.get("unit", ""),
            "role": user["role"],
            "token": token,
        },
    }


@app.post("/api/change-password")
def change_password(req: ChangePasswordRequest, session: Dict[str, Any] = Depends(current_session)):
    """
    เปลี่ยนรหัสผ่านของบัญชีตัวเอง เก็บลงชีตเป็น sha256$ เสมอ ไม่ว่าของเดิมจะเป็นแบบไหน
    จึงเป็นทางที่บัญชีรหัส Plaintext เดิมย้ายมาเป็นแบบเข้ารหัสได้ด้วย
    """
    username = req.username.strip()

    # เปลี่ยนได้เฉพาะบัญชีตัวเอง ต่อให้ถือ token ของ ผบก. ก็ตั้งรหัสให้คนอื่นไม่ได้
    if username.lower() != str(session.get("u") or "").strip().lower():
        raise HTTPException(status_code=403, detail="เปลี่ยนรหัสผ่านได้เฉพาะบัญชีของตัวเองเท่านั้น")

    if len(req.newPassword) < MIN_PASSWORD_LENGTH:
        return {"status": "error", "message": f"รหัสผ่านใหม่ต้องยาวอย่างน้อย {MIN_PASSWORD_LENGTH} ตัวอักษร"}

    if req.newPassword == req.oldPassword:
        return {"status": "error", "message": "รหัสผ่านใหม่ต้องไม่ซ้ำกับรหัสผ่านเดิม"}

    try:
        user = user_service.get_user(username)
        if not user or not verify_password(username, req.oldPassword, user.get("password", "")):
            return {"status": "error", "message": "รหัสผ่านปัจจุบันไม่ถูกต้อง หรือไม่พบข้อมูลบัญชีผู้ใช้"}

        if not user_service.update_password(username, hash_password(username, req.newPassword)):
            return {"status": "error", "message": "ไม่พบข้อมูลบัญชีผู้ใช้"}
    except UserDirectoryUnavailable as exc:
        logger.error("เปลี่ยนรหัสผ่านไม่ได้: %s", exc)
        raise HTTPException(status_code=503, detail="ระบบเข้าถึงรายชื่อผู้ใช้ไม่ได้ในขณะนี้") from exc
    except SheetWriteError as exc:
        logger.error("เขียนรหัสผ่านใหม่ไม่สำเร็จ: %s", exc)
        raise HTTPException(status_code=502, detail=f"บันทึกรหัสผ่านใหม่ไม่สำเร็จ: {exc}") from exc

    return {
        "status": "success",
        "message": "เปลี่ยนรหัสผ่านเป็นรหัสใหม่เรียบร้อยแล้ว กรุณาเข้าสู่ระบบใหม่อีกครั้ง",
    }


@app.get("/api/dropdowns/units")
def units_dropdown(station: Optional[str] = None, session: Dict[str, Any] = Depends(current_session)):
    """หน่วยบริการของสถานีนั้น อ่านจาก STATION_CONFIG (เทียบเท่า getUnitDropdown ใน JS)"""
    station_id = authorized_station_id(station, session)

    # get_station_data สร้างชื่อให้เองเมื่อไม่รู้จักสถานี ซึ่งดีตอนเขียนรายงาน แต่ตรงนี้
    # จะกลายเป็น dropdown ที่มีหน่วยสมมติอยู่หนึ่งรายการ บอกไปตรง ๆ ว่าไม่รู้จักดีกว่า
    if station_id not in get_station_config():
        raise HTTPException(status_code=404, detail=f"ไม่รู้จักสถานี {station_id} กรุณาแจ้งผู้ดูแลระบบ")

    return get_station_data(station_id).get("units") or []


@app.get("/api/dropdowns/users")
def users_dropdown(station: Optional[str] = None, session: Dict[str, Any] = Depends(current_session)):
    """ชื่อเจ้าหน้าที่ในขอบเขตที่สถานีนั้นมองเห็นได้"""
    station_id = authorized_station_id(station, session)
    try:
        return user_service.list_names_for_station(station_id)
    except UserDirectoryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/dropdowns/user-phones")
def user_phones_dropdown(station: Optional[str] = None, session: Dict[str, Any] = Depends(current_session)):
    """ชื่อเจ้าหน้าที่ -> เบอร์โทร ใช้เติมเบอร์อัตโนมัติเมื่อเลือกผู้รายงาน"""
    station_id = authorized_station_id(station, session)
    try:
        return user_service.phone_map_for_station(station_id)
    except UserDirectoryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/dropdowns/charges")
def charges_dropdown(_: Dict[str, Any] = Depends(current_session)):
    """รายการข้อหาที่ยังใช้งานอยู่ ใช้ร่วมกันทุกสถานีจึงไม่ต้องกรองตามสถานี"""
    try:
        return reference_service.get_charges()
    except ReferenceDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/dropdowns/charges-grouped")
def charges_grouped(_: Dict[str, Any] = Depends(current_session)):
    """
    ข้อหาที่จัดกลุ่มตาม พ.ร.บ. แล้ว (requirement ข้อ 14)

    คืนทั้งแบบจัดกลุ่มและแบบรายชื่อล้วน เพื่อให้หน้าเว็บสลับเปิด/ปิดการจัดกลุ่มได้
    โดยไม่ต้องยิงซ้ำ — การอ่านชีตหนึ่งครั้งกินโควตาเท่ากันไม่ว่าจะขอรูปแบบไหน
    """
    try:
        detailed = reference_service.get_charges_detailed()
    except ReferenceDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "status": "success",
        "data": {
            "groups": charge_group_service.grouped(detailed),
            "flat": [item["name"] for item in detailed],
            "groupOrder": charge_group_service.GROUP_ORDER,
        },
    }


def _name_lookup() -> Dict[str, str]:
    """username -> ชื่อจริง ไว้แสดงชื่อผู้ส่งในคิวอนุมัติแทนชื่อบัญชี"""
    try:
        return {name: user.get("fullName", "") for name, user in user_service.get_all_users().items()}
    except UserDirectoryUnavailable:
        # ชื่อที่แสดงสวยขึ้นไม่คุ้มกับการทำให้คิวอนุมัติทั้งหน้าใช้ไม่ได้
        logger.warning("อ่านรายชื่อผู้ใช้ไม่ได้ คิวอนุมัติจะแสดงเป็นชื่อบัญชีแทน")
        return {}


def _resolve_record(sheet_name: str, record_id: str, session: Dict[str, Any]) -> Dict[str, Any]:
    """หาแถวและตรวจว่า session นี้แตะรายการของสถานีนั้นได้จริง"""
    if sheet_name not in query_service.APPROVABLE_TABLES:
        raise HTTPException(status_code=400, detail=f"ตาราง {sheet_name} ไม่ใช่รายการที่ต้องอนุมัติ")

    station_id = str(session.get("s") or "").strip()
    try:
        record = query_service.find_record(station_id, sheet_name, record_id)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not check_station_match(station_id, record.get(query_service.COL_STATION_ID, "")):
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์จัดการรายการของสถานีอื่น")

    return record


@app.get("/api/my-pending")
def my_pending(username: Optional[str] = None, session: Dict[str, Any] = Depends(current_session)):
    """รายการของตัวเองที่ยังรออนุมัติ (เทียบเท่า getMyPendingItems ใน JS)"""
    own = str(session.get("u") or "").strip()
    requested = str(username or "").strip() or own

    # ประวัติของตัวเองเท่านั้น ไม่งั้นใครก็ดูได้ว่าคนอื่นส่งอะไรค้างไว้บ้าง
    if requested.lower() != own.lower():
        raise HTTPException(status_code=403, detail="ดูได้เฉพาะประวัติการส่งของตัวเองเท่านั้น")

    try:
        data = query_service.pending_for_user(str(session.get("s") or ""), own)
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"status": "success", "data": data}


@app.get("/api/station-pending")
def station_pending(station: Optional[str] = None, session: Dict[str, Any] = Depends(current_session)):
    """คิวอนุมัติของสถานี แยกรายงานทั่วไปกับน้ำมัน พร้อมยอดสรุปสำหรับการ์ด KPI"""
    station_id = authorized_station_id(station, session)

    try:
        data = query_service.station_overview(station_id, _name_lookup())
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"status": "success", "data": data}


@app.get("/api/missions")
def missions(
    unit: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    station: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """ภารกิจของหน่วยในช่วงวันที่ (เทียบเท่า getMissionsForView ใน JS)"""
    station_id = authorized_station_id(station, session)
    try:
        data = query_service.missions_for_unit(station_id, unit or "", start or "", end or "")
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@app.get("/api/daily-summary")
def daily_summary(
    station: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """ยอดสรุปของสถานีเดียวในช่วงวันที่ ใช้เติมแท็บสรุปยอดส่งของฟอร์มรายงานประจำวัน"""
    station_id = authorized_station_for_stats(station, session)
    try:
        data = query_service.daily_summary(station_id, start or "", end or "")
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@app.get("/api/division-summary")
def division_summary(
    station: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """ยอดทั้งกองกำกับการแยกรายสถานี สำหรับหน้า ฝอ.กก. และหน้าผู้กำกับการ"""
    station_id = authorized_station_for_stats(station, session)

    # เห็นภาพรวมทั้ง กก. ได้เฉพาะระดับ ฝอ.กก. ขึ้นไป สถานีเดียวใช้ /api/daily-summary
    if str(session.get("r") or "") not in DIVISION_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ดูภาพรวมระดับกองกำกับการ")

    try:
        data = query_service.division_summary(station_id, start or "", end or "")
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@app.get("/api/national-summary")
def national_summary(
    start: Optional[str] = None,
    end: Optional[str] = None,
    includeArchived: bool = False,
    session: Dict[str, Any] = Depends(current_session),
):
    """
    ภาพรวมของ บก.ทล. อ่านจาก tb_National_Summary ที่งาน cron รวมยอดไว้แล้ว
    ไม่ได้อ่านชีตของ กก. สด ๆ เพราะ 8 กก. x 6 ตาราง ชนโควตาทันทีที่เปิดพร้อมกันสองคน

    ตาม requirement ข้อ 3 ค่าเริ่มต้นนับเฉพาะ กก.8 ส่วน กก.1-7 ยังถูกรวมยอดและเก็บครบ
    ทุกวันเหมือนเดิม แต่ไม่นำขึ้นภาพรวมนี้ ส่ง `includeArchived=true` เพื่อเรียกดู
    ข้อมูลสำรองของทุก กก. ย้อนหลัง
    """
    if str(session.get("r") or "") not in NATIONAL_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ดูภาพรวมระดับประเทศ")

    try:
        data = national_service.national_summary(start or "", end or "", include_archived=includeArchived)
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


# ตารางที่อยู่ในชีตกลางไฟล์เดียว ไม่ได้อยู่ในชีตของแต่ละ กก. จึงไม่ควรถูกรายงานว่า
# "ขาด" ตอนตรวจสุขภาพฐานข้อมูลราย กก. — ไม่งั้นทุกกองจะขึ้นว่าขาดตารางตลอดเวลา
MASTER_ONLY_TABLES = {"tb_Users", "tb_National_Summary"}


def _cron_authorized(secret: Optional[str]) -> bool:
    """
    ให้ตัวตั้งเวลาภายนอกเรียกได้ด้วย shared secret แทน session

    Session token หมดอายุใน 24 ชั่วโมง ตัวตั้งเวลาจึงถือ token ไว้ไม่ได้ และ Render
    Cron Jobs เป็นบริการที่ต้องเสียเงิน ทางนี้เลยใช้ได้กับแผนฟรีด้วย
    """
    expected = os.getenv("CRON_SECRET", "").strip()
    return bool(expected) and hmac.compare_digest(expected, str(secret or "").strip())


def _run_aggregate(start: str, end: str) -> None:
    """รวมยอดในเบื้องหลัง — งานนี้ใช้เวลาเป็นนาทีเมื่อครบ 8 กก. จึงไม่ควรให้ผู้เรียกรอ"""
    if not _aggregate_lock.acquire(blocking=False):
        logger.warning("มีรอบรวมยอดทำงานอยู่แล้ว ข้ามรอบนี้ไป")
        _record_aggregate_outcome("skipped", start, end, detail="มีรอบก่อนหน้ายังทำงานอยู่")
        return
    try:
        result = national_service.aggregate_national(start, end)
        logger.info("รวมยอดระดับประเทศเสร็จแล้ว: %s", result)
        _record_aggregate_outcome("ok", start, end, result=result)
    except Exception as exc:
        logger.exception("รวมยอดระดับประเทศไม่สำเร็จ")
        _record_aggregate_outcome("failed", start, end, detail=f"{type(exc).__name__}: {exc}")
    finally:
        _aggregate_lock.release()


def _record_aggregate_outcome(
    status: str,
    start: str,
    end: str,
    result: Optional[Dict[str, Any]] = None,
    detail: str = "",
) -> None:
    """
    เก็บผลรอบล่าสุดไว้ให้ /api/admin/aggregate-status อ่าน

    endpoint สั่งรวมยอดตอบ 202 ตั้งแต่ยังไม่เริ่มทำงาน ตัวตั้งเวลาจึงเห็นว่าสำเร็จเสมอ
    แม้งานจริงจะล้มทั้งรอบ ที่ผ่านมาความล้มเหลวไปโผล่แค่ใน log ของ Render ซึ่งไม่มีใคร
    เปิดดู กว่าจะรู้ตัวคือหน้า dashboard แสดงยอดผิดมาแล้วหลายวัน

    เก็บในหน่วยความจำพอ ค่าที่ต้องการคือ "รอบล่าสุดผ่านไหม" ไม่ใช่ประวัติย้อนหลัง
    service restart แล้วค่าหายกลายเป็น never ซึ่งตัวตรวจก็ควรถือว่ายังไม่ผ่านอยู่ดี
    """
    with _aggregate_status_lock:
        _last_aggregate.update(
            {
                "status": status,
                "start": start,
                "end": end,
                "detail": detail,
                "result": result or {},
                "finishedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )


@app.post("/api/admin/aggregate-national", status_code=202)
def trigger_aggregate_national(
    background: BackgroundTasks,
    days: int = 7,
    x_cron_secret: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None),
):
    """
    สั่งรวมยอดระดับประเทศ ตอบกลับทันทีแล้วทำงานต่อเบื้องหลัง

    เรียกได้สองทาง: ผู้ใช้ระดับ บก. ที่ล็อกอินอยู่ หรือตัวตั้งเวลาภายนอกที่ส่ง
    header `x-cron-secret` ตรงกับ CRON_SECRET
    """
    if not _cron_authorized(x_cron_secret):
        session = verify_session_token(x_token or "")
        if not session:
            raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบหรือส่ง x-cron-secret ที่ถูกต้อง")
        if str(session.get("r") or "") not in NATIONAL_VIEW_ROLES:
            raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์สั่งรวมยอดระดับประเทศ")

    start, end = national_service.default_range(max(1, min(days, 90)))
    background.add_task(_run_aggregate, start, end)
    return {"status": "accepted", "message": f"เริ่มรวมยอด {start} ถึง {end} แล้ว", "start": start, "end": end}


def _run_report_cache(dates: List[str]) -> None:
    """สร้างแคชในเบื้องหลัง — สแกน 2 ตาราง x 8 กก. ใช้เวลาเป็นนาที"""
    if not _report_cache_lock.acquire(blocking=False):
        logger.warning("มีรอบสร้างแคชรายงานทำงานอยู่แล้ว ข้ามรอบนี้ไป")
        return
    try:
        result = report_cache_service.refresh(dates)
        logger.info("สร้างแคชรายงานเสร็จแล้ว: %s", result)
    except Exception:
        logger.exception("สร้างแคชรายงานไม่สำเร็จ")
    finally:
        _report_cache_lock.release()


@app.post("/api/admin/report-cache/refresh", status_code=202)
def refresh_report_cache(
    background: BackgroundTasks,
    days: int = 7,
    x_cron_secret: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None),
):
    """
    สั่งสร้างแคชสถิติรายงานย้อนหลัง N วัน ตอบกลับทันทีแล้วทำต่อเบื้องหลัง

    เรียกได้สองทาง เหมือน aggregate-national: ผู้ใช้ระดับ บก. หรือตัวตั้งเวลาที่ส่ง
    x-cron-secret มา
    """
    if not _cron_authorized(x_cron_secret):
        session = verify_session_token(x_token or "")
        if not session or str(session.get("r") or "") not in NATIONAL_VIEW_ROLES:
            raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบหรือส่ง x-cron-secret ที่ถูกต้อง")

    start, end = national_service.default_range(max(1, min(days, 90)))
    dates = report_cache_service.date_range(start, end)
    background.add_task(_run_report_cache, dates)
    return {"status": "accepted", "message": f"เริ่มสร้างแคช {start} ถึง {end} แล้ว",
            "start": start, "end": end, "days": len(dates)}


@app.get("/api/reports/catalog/exportable")
def reports_exportable(session: Dict[str, Any] = Depends(current_session)):
    """แบบฟอร์มที่ออกเป็น Excel ได้ตอนนี้"""
    if str(session.get("r") or "") not in NATIONAL_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ออกรายงานระดับประเทศ")
    return {"status": "success", "data": report_export_service.available_reports()}


@app.get("/api/reports/export")
def reports_export(
    reportKey: str,
    start: str = "",
    end: str = "",
    session: Dict[str, Any] = Depends(current_session),
):
    """ออกรายงานตามแบบฟอร์มเป็นไฟล์ Excel"""
    if str(session.get("r") or "") not in NATIONAL_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ออกรายงานระดับประเทศ")

    try:
        content = report_export_service.build_workbook(reportKey, start, end)
    except report_export_service.ReportNotSupported as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    filename = f"{reportKey}_{start}_{end}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        # ชื่อไฟล์เป็น ASCII ล้วนอยู่แล้ว จึงไม่ต้องเข้ารหัสแบบ RFC 5987
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class ReferenceUpsertRequest(BaseModel):
    """values คือค่าทั้งแถวตามชื่อคอลัมน์ ช่องที่ไม่ส่งมาจะคงของเดิม"""

    model_config = ConfigDict(extra="forbid")

    values: Dict[str, str]
    originalKey: Optional[str] = None


class ReferenceActiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    active: bool


def _require_hq(session: Dict[str, Any]) -> None:
    if str(session.get("r") or "") not in NATIONAL_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์แก้ข้อมูลอ้างอิงของระบบ")


@app.get("/api/admin/reference/{kind}")
def admin_reference_list(kind: str, session: Dict[str, Any] = Depends(current_session)):
    """ตารางอ้างอิงที่แก้ได้ — ข้อหา / ประเภทของกลาง / รายการรายงาน"""
    _require_hq(session)
    try:
        rows = reference_admin_service.list_rows(kind)
    except reference_admin_service.ReferenceTableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (SheetNotConfigured, SheetWriteError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    spec = reference_admin_service.REFERENCE_TABLES[kind]
    return {
        "status": "success",
        "data": rows,
        "keyColumn": spec["key"],
        "activeColumn": spec["active"],
        "label": spec["label"],
    }


@app.post("/api/admin/reference/{kind}")
def admin_reference_upsert(
    kind: str,
    req: ReferenceUpsertRequest,
    session: Dict[str, Any] = Depends(current_session),
):
    """เพิ่มหรือแก้แถวในตารางอ้างอิง"""
    _require_hq(session)
    try:
        message = reference_admin_service.upsert(kind, req.values, req.originalKey)
    except reference_admin_service.ReferenceTableError as exc:
        return {"status": "error", "message": str(exc)}
    except (SheetNotConfigured, SheetWriteError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "success", "message": message}


@app.post("/api/admin/reference/{kind}/active")
def admin_reference_set_active(
    kind: str,
    req: ReferenceActiveRequest,
    session: Dict[str, Any] = Depends(current_session),
):
    """
    เปิด/ปิดใช้งานแถว ใช้แทนการลบ

    ของเดิมลบแถวทิ้ง แต่ข้อหาที่ถูกลบยังถูกอ้างอยู่ในรายงานเก่า ปิดใช้งานได้ผลเหมือน
    กันในสายตาคนกรอกฟอร์ม แต่ข้อมูลเดิมยังตามรอยได้และกดคืนได้
    """
    _require_hq(session)
    try:
        message = reference_admin_service.set_active(kind, req.key, req.active)
    except reference_admin_service.ReferenceTableError as exc:
        return {"status": "error", "message": str(exc)}
    except (SheetNotConfigured, SheetWriteError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "success", "message": message}


@app.get("/api/map/points")
def map_points(
    station: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    layers: Optional[str] = None,
    charge: Optional[str] = None,
    unit: Optional[str] = None,
    stationFilter: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """
    พิกัดสำหรับหน้าแผนที่ (requirement ข้อ 4)

    `layers` คั่นด้วยลูกน้ำ (crime,checkpoint,accident) ไม่ส่งมา = เอาทั้งสามชั้น
    หน้าเว็บส่งเฉพาะชั้นที่เปิดอยู่ ชั้นที่ผู้ใช้ปิดไว้จึงไม่ถูกอ่านจากชีตเลย

    ขอบเขตการมองเห็นยึดจาก session ตามกติกาเดียวกับหน้าอื่น สถานีเห็นของตัวเอง
    ระดับ ฝอ.กก. ขึ้นไปเห็นทุกสถานีในกองตัวเอง
    """
    station_id = authorized_station_for_stats(station, session)
    wanted = [name.strip() for name in (layers or "").split(",") if name.strip()]

    if stationFilter and not check_station_match(station_id, str(stationFilter).strip()):
        raise HTTPException(status_code=403, detail=f"ไม่มีสิทธิ์ดูข้อมูลของสถานี {stationFilter}")

    try:
        data = map_service.map_points(
            station_id,
            start=start or "",
            end=end or "",
            layers=wanted or None,
            charge=charge or "",
            unit=unit or "",
            station_filter=str(stationFilter or "").strip(),
        )
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"status": "success", "data": data}


@app.get("/api/search/division")
def search_division(
    station: Optional[str] = None,
    keyword: str = "",
    start: str = "",
    end: str = "",
    session: Dict[str, Any] = Depends(current_session),
):
    """ค้นหาเชิงลึกในกองกำกับ — ปุ่ม "แกะรอยผลงาน" ของผู้กำกับการ"""
    if str(session.get("r") or "") not in DIVISION_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ค้นหาข้อมูลระดับกองกำกับ")
    if not keyword.strip():
        return {"status": "error", "message": "กรุณาระบุคำค้นหา"}

    station_id = authorized_station_id(station, session)
    try:
        data = search_service.search_division(station_id, keyword, start, end)
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@app.get("/api/search/national")
def search_national(
    keyword: str = "",
    start: str = "",
    end: str = "",
    session: Dict[str, Any] = Depends(current_session),
):
    """ค้นหาข้ามทุก กก. — ปุ่ม "ค้นหาทุกกอง" ของ ผบก. ทำงานเฉพาะตอนกด ไม่โหลดเอง"""
    if str(session.get("r") or "") not in NATIONAL_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ค้นหาข้อมูลระดับประเทศ")
    if not keyword.strip():
        return {"status": "error", "message": "กรุณาระบุคำค้นหา"}

    try:
        data = search_service.search_national(keyword, start, end)
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


class UserProfileUpdateRequest(BaseModel):
    """แก้ได้เฉพาะชื่อจริงกับเบอร์โทร ดู user_service.EDITABLE_COLUMNS ว่าทำไม"""

    model_config = ConfigDict(extra="forbid")

    username: str
    fullName: Optional[str] = None
    phone: Optional[str] = None


@app.get("/api/admin/users")
def admin_list_users(session: Dict[str, Any] = Depends(current_session)):
    """
    ทำเนียบผู้ใช้ทั้งหมดสำหรับหน้าจัดการผู้ใช้งานของ บก.

    ไม่ส่งคอลัมน์ Password ออกไปแม้จะ hash แล้ว หน้าเว็บไม่มีอะไรต้องใช้ค่านั้น
    และ hash ที่หลุดออกไปคือของที่เอาไปไล่เดารหัสแบบออฟไลน์ได้
    """
    if str(session.get("r") or "") not in NATIONAL_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ดูทำเนียบผู้ใช้ทั้งหมด")

    try:
        users = user_service.get_all_users()
    except user_service.UserDirectoryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    data = [
        {k: v for k, v in user.items() if k != "password"}
        for user in sorted(users.values(), key=lambda u: str(u.get("username", "")))
    ]
    return {"status": "success", "data": data}


@app.post("/api/admin/users/update")
def admin_update_user(req: UserProfileUpdateRequest, session: Dict[str, Any] = Depends(current_session)):
    """แก้ชื่อจริง/เบอร์โทรของบัญชี — ใช้เติมชื่อแทนบัญชีที่สร้างไว้เป็น placeholder"""
    if str(session.get("r") or "") not in NATIONAL_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์แก้ข้อมูลผู้ใช้")

    if req.fullName is None and req.phone is None:
        return {"status": "error", "message": "ไม่ได้ระบุข้อมูลที่จะแก้"}

    try:
        changed = user_service.update_profile(req.username, req.fullName, req.phone)
    except user_service.UserDirectoryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not changed:
        return {"status": "error", "message": f"ไม่พบบัญชี {req.username}"}
    return {"status": "success", "message": f"แก้ข้อมูลบัญชี {req.username} เรียบร้อยแล้ว"}


@app.get("/api/admin/aggregate-status")
def aggregate_status(
    x_cron_secret: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None),
):
    """
    ผลรอบรวมยอดล่าสุด สำหรับให้ตัวตั้งเวลาตรวจว่ารอบที่เพิ่งสั่งไปทำสำเร็จจริง

    ต้องมีเพราะ POST /api/admin/aggregate-national ตอบ 202 ก่อนงานจะเริ่ม ตัวตั้งเวลา
    ที่ดูแค่ status code จึงขึ้นเขียวทุกครั้งแม้การรวมยอดล้มทั้งรอบ

    status: ok = รอบล่าสุดสำเร็จ | failed = ล้ม ดู detail | skipped = ชนรอบก่อนหน้า
            never = ยังไม่เคยรันตั้งแต่ service เริ่ม (รวมถึงกรณีเพิ่ง restart)
    """
    if not _cron_authorized(x_cron_secret):
        session = verify_session_token(x_token or "")
        if not session or str(session.get("r") or "") not in NATIONAL_VIEW_ROLES:
            raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบหรือส่ง x-cron-secret ที่ถูกต้อง")

    with _aggregate_status_lock:
        return dict(_last_aggregate)


@app.get("/api/records/detail")
def record_detail(
    sheetName: str,
    recordId: str,
    session: Dict[str, Any] = Depends(current_session),
):
    """
    รายละเอียดเต็มของรายการหนึ่งใบ พร้อมลิงก์ไฟล์แนบ (requirement ข้อ 9)

    ใช้ทั้งฝั่งแอดมินที่ต้องตรวจก่อนอนุมัติ และฝั่งเจ้าของรายการที่จะกดแก้ไข
    ขอบเขตการมองเห็นยึดจาก `_resolve_record` ตัวเดียวกับที่การอนุมัติใช้
    """
    record = _resolve_record(sheetName, recordId, session)

    try:
        data = query_service.record_detail(
            str(session.get("s") or ""), sheetName, recordId
        )
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # เจ้าของรายการเท่านั้นที่แก้ได้ และแก้ได้เฉพาะตอนยังรออนุมัติ (ข้อ 10)
    data["canEdit"] = (
        record.get(query_service.COL_ACTION_BY, "") == str(session.get("u") or "").strip()
        and record.get(query_service.COL_STATUS) == query_service.STATUS_PENDING
    )
    data["editableFields"] = [
        column
        for column in get_columns(sheetName)
        if column not in query_service.PROTECTED_COLUMNS
        and column not in query_service.ATTACHMENT_COLUMNS
    ]
    return {"status": "success", "data": data}


@app.post("/api/records/update")
def update_record(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """
    แก้ไขรายการของตัวเองที่ยังรออนุมัติ (requirement ข้อ 10)

    **เจ้าของรายการเท่านั้น** แอดมินที่เห็นรายการนี้ก็แก้ไม่ได้ เพราะการที่คนอื่นแก้
    เนื้อรายงานแล้วชื่อผู้ส่งยังเป็นชื่อเดิม ทำให้ร่องรอยความรับผิดชอบเพี้ยน
    ถ้าแอดมินเห็นว่าผิดให้ตีกลับ (`/api/records/cancel`) ให้เจ้าตัวส่งใหม่
    """
    sheet_name = str(payload.get("sheetName") or "").strip()
    record_id = str(payload.get("recordId") or "").strip()
    updates = payload.get("updates")

    if not isinstance(updates, dict) or not updates:
        raise HTTPException(status_code=400, detail="ไม่มีข้อมูลที่จะแก้ไข")

    record = _resolve_record(sheet_name, record_id, session)

    if record.get(query_service.COL_ACTION_BY, "") != str(session.get("u") or "").strip():
        raise HTTPException(status_code=403, detail="แก้ไขได้เฉพาะรายการที่ตัวเองส่งเท่านั้น")

    try:
        diff = query_service.update_record(record, sheet_name, sanitize_form_data(updates))
    except query_service.NotEditable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not diff:
        return {"status": "success", "message": "ไม่มีช่องไหนเปลี่ยนแปลง", "changed": 0}

    audit_service.record(
        session,
        audit_service.ACTION_UPDATE,
        sheet_name,
        record_id,
        before={key: value["from"] for key, value in diff.items()},
        after={key: value["to"] for key, value in diff.items()},
        note="เจ้าของรายการแก้ไขเอง",
        station_id=record.get(query_service.COL_STATION_ID),
    )
    return {"status": "success", "message": f"แก้ไข {len(diff)} ช่องเรียบร้อยแล้ว", "changed": len(diff)}


@app.post("/api/records/approve")
def approve_record(req: RecordActionRequest, session: Dict[str, Any] = Depends(current_session)):
    """อนุมัติรายการ เปลี่ยน Sys_Status เป็น Approved"""
    if str(session.get("r") or "") not in APPROVER_ROLES:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์อนุมัติรายงาน")

    record = _resolve_record(req.sheetName, req.recordId, session)
    if record.get(query_service.COL_STATUS) != query_service.STATUS_PENDING:
        return {
            "status": "error",
            "message": f"รายการนี้ไม่ได้อยู่ในสถานะรออนุมัติแล้ว (ขณะนี้: {record.get(query_service.COL_STATUS)})",
        }

    try:
        query_service.set_status(record, req.sheetName, query_service.STATUS_APPROVED, True)
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    audit_service.record(
        session,
        audit_service.ACTION_APPROVE,
        req.sheetName,
        req.recordId,
        before={query_service.COL_STATUS: query_service.STATUS_PENDING},
        after={query_service.COL_STATUS: query_service.STATUS_APPROVED},
        station_id=record.get(query_service.COL_STATION_ID),
    )
    return {"status": "success", "message": "อนุมัติรายการเรียบร้อย"}


@app.post("/api/records/cancel")
def cancel_record(req: RecordActionRequest, session: Dict[str, Any] = Depends(current_session)):
    """
    ยกเลิกรายการ เปลี่ยน Sys_Status เป็น Canceled และปิด Sys_IsActive

    เจ้าของรายการยกเลิกของตัวเองได้ก่อนถูกอนุมัติ ส่วนแอดมินตีกลับของคนอื่นในสถานีได้
    """
    record = _resolve_record(req.sheetName, req.recordId, session)

    own = str(session.get("u") or "").strip()
    is_owner = record.get(query_service.COL_ACTION_BY, "") == own
    is_approver = str(session.get("r") or "") in APPROVER_ROLES

    if not (is_owner or is_approver):
        raise HTTPException(status_code=403, detail="ยกเลิกได้เฉพาะรายการที่ตัวเองส่งเท่านั้น")

    if record.get(query_service.COL_STATUS) == query_service.STATUS_CANCELED:
        return {"status": "error", "message": "รายการนี้ถูกยกเลิกไปแล้ว"}

    try:
        query_service.set_status(record, req.sheetName, query_service.STATUS_CANCELED, False)
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    audit_service.record(
        session,
        audit_service.ACTION_CANCEL,
        req.sheetName,
        req.recordId,
        before={query_service.COL_STATUS: record.get(query_service.COL_STATUS)},
        after={query_service.COL_STATUS: query_service.STATUS_CANCELED},
        note="เจ้าของรายการยกเลิกเอง" if is_owner else "แอดมินตีกลับ",
        station_id=record.get(query_service.COL_STATION_ID),
    )
    return {"status": "success", "message": "ยกเลิกรายการนี้เรียบร้อยแล้ว"}


@app.post("/api/reports/daily")
def submit_daily_report(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """
    บันทึกรายงานประจำวัน (OP)

    `officers` ในคำขอนี้คือ **ผู้ร่วมออก ว.4 ที่เพิ่มเข้ามา** (requirement ข้อ 11)
    ไม่ใช่รายชื่อทั้งหมดเหมือนที่ `/api/reports/other-duty` ใช้ เพราะสามตำแหน่งประจำ
    (ผู้ปฏิบัติประจำหน่วย พลขับ พงว.) มีช่องของตัวเองอยู่แล้วใน formData
    """
    station_id = authorized_station(req.formData, session)
    record_id = generate_record_id("OP")
    attachments = prepare_attachments(req.files, station_id, record_id, str(req.formData.get("unitId", "")))

    prepared = prepare_daily_report(
        req.formData,
        folder_url=attachments["folderUrl"],
        record_id=record_id,
        extra_officers=req.officers or [],
    )
    return submit(prepared, attachments, "บันทึกข้อมูลและเตรียมส่งรายงานเรียบร้อยแล้ว")


@app.post("/api/reports/checkpoint")
def submit_checkpoint_report(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """บันทึกรายงานตั้งด่าน (CHK)"""
    station_id = authorized_station(req.formData, session)
    record_id = generate_record_id("CHK")
    attachments = prepare_attachments(req.files, station_id, record_id, str(req.formData.get("unitId", "")))

    prepared = prepare_checkpoint_report(req.formData, folder_url=attachments["folderUrl"], record_id=record_id)
    return submit(prepared, attachments, "บันทึกรายงานตั้งด่านเรียบร้อยแล้ว")


@app.post("/api/reports/arrest")
def submit_arrest_report(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """บันทึกรายงานการจับกุม (ARR)"""
    station_id = authorized_station(req.formData, session)
    record_id = generate_record_id("ARR")
    attachments = prepare_attachments(req.files, station_id, record_id, str(req.formData.get("unitId", "")))

    prepared = prepare_arrest_report(
        req.formData,
        team_array=req.teamArray or [],
        suspect_array=req.suspectArray or [],
        charge_array=req.chargeArray or [],
        seized_items=req.seizedItems or [],
        folder_url=attachments["folderUrl"],
        record_id=record_id,
    )
    return submit(prepared, attachments, "บันทึกรายงานการจับกุมเรียบร้อยแล้ว")


@app.post("/api/reports/daily-summary")
def submit_daily_summary(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """
    สรุปยอดส่ง กก. (HQ-SUM) เขียนลง tb_HQ_Summary

    ยอดในนี้มาจาก /api/daily-summary ที่ฟอร์มเรียกไปคำนวณให้ก่อนแล้ว ตรงนี้เป็นการ
    ยืนยันส่งเท่านั้น จึงไม่คำนวณซ้ำ — เจ้าหน้าที่แก้ตัวเลขก่อนส่งได้ตามระบบเดิม
    """
    authorized_station(req.formData, session)
    prepared = prepare_hq_summary(req.formData)
    return submit(prepared, {"stored": True, "count": 0}, "บันทึกยอดสรุปส่ง กก. เรียบร้อยแล้ว")


@app.post("/api/reports/mission-summary")
def submit_mission_summary(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """
    สรุปภารกิจส่งเข้า LINE — ไม่เขียนลงตาราง เพราะเป็นการรวมภารกิจที่บันทึกไว้แล้ว
    มาแจ้งซ้ำ ไม่ใช่รายการใหม่ (ตรงตามที่ sendMissionSummaryLine ใน JS ทำ)
    """
    authorized_station(req.formData, session)
    prepared = build_mission_summary(req.formData, req.missions or [])

    if prepared["lineGroupId"]:
        line_result = push_line_message(prepared["lineMessage"], prepared["lineGroupId"])
        if line_result.get("status") == "error":
            logger.warning("ส่งสรุปภารกิจเข้า LINE ไม่สำเร็จ: %s", line_result.get("message"))

    return {
        "status": "success",
        "message": f"สรุปภารกิจ {prepared['missionCount']} รายการเรียบร้อยแล้ว",
        "lineText": prepared["lineMessage"],
    }


@app.post("/api/reports/auto-arrest")
def submit_auto_arrest(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """
    สร้างเอกสารจับกุม — ไม่เขียนลงตาราง คืนไฟล์ .docx กลับไปให้ดาวน์โหลดเลย

    รายการนี้ไม่ผูกกับสถานีในชีต จึงตรวจแค่ว่ามี session ที่ใช้ได้ ไม่ต้องมี stationId

    **สร้างในเครื่อง ไม่ผ่าน Google Docs** (`docx_service`) ของเดิมคัดลอกแม่แบบบน Drive
    แล้วสั่ง Docs API แทนที่ข้อความ ซึ่งต้องต่อเน็ตออก Google กินโควตาที่ทั้งระบบใช้ร่วมกัน
    ทิ้งสำเนาไว้บน Drive ทุกครั้งที่กดปุ่ม และผูกกับบัญชี OAuth บัญชีเดียว

    ยังเหลือทางเดิมไว้เผื่อเครื่องไหนยังไม่ได้ลง python-docx — ถ้าตัวสร้างในเครื่องใช้ไม่ได้
    จะถอยไปใช้ Google Docs แล้วคืน `links` แบบเดิม หน้าเว็บรองรับทั้งสองรูปแบบ
    """
    if not req.suspectArray:
        raise HTTPException(status_code=400, detail="กรุณาระบุผู้ต้องหาอย่างน้อยหนึ่งคน")

    if docx_service.is_available():
        try:
            documents = docx_service.build_arrest_documents(req.formData, req.suspectArray)
        except docx_service.TemplateMissing as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        # ตัวยึดที่ค้างแปลว่าแม่แบบกับโค้ดหลุดจากกัน บอกไปตามตรง อย่าปล่อยให้เจ้าหน้าที่
        # ไปเจอ <<OFFENSE>> เองตอนพิมพ์เอกสารส่งพนักงานสอบสวน
        leftover = sorted({p for doc in documents for p in doc["leftover"]})
        warning = (
            f"แม่แบบมีช่องที่ระบบยังไม่ได้ส่งค่าให้ {len(leftover)} ช่อง: {', '.join(leftover)}"
            if leftover else None
        )
        return {
            "status": "success",
            "message": f"สร้างเอกสารเรียบร้อยแล้ว {len(documents)} ฉบับ",
            "warning": warning,
            "files": [
                {
                    "name": doc["name"],
                    "filename": doc["filename"],
                    "mime": docx_service.DOCX_MIME,
                    "data": base64.b64encode(doc["data"]).decode("ascii"),
                }
                for doc in documents
            ],
        }

    logger.warning("ไม่มี python-docx หรือไฟล์แม่แบบ ถอยไปใช้ Google Docs")
    try:
        links = docs_service.generate_arrest_documents(req.formData, req.suspectArray)
    except TemplateNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DocumentError as exc:
        logger.error("สร้างเอกสารจับกุมไม่สำเร็จ: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "status": "success",
        "message": f"สร้างเอกสารเรียบร้อยแล้ว {len(links)} ฉบับ",
        "links": links,
    }


def handle_submission(
    req: ReportSubmissionRequest,
    session: Dict[str, Any],
    prefix: str,
    build,
    message: str,
) -> Dict[str, Any]:
    """
    ขั้นตอนเดียวกันทุกรายงาน: ตรวจสิทธิ์สถานี -> สร้างรหัส -> อัปโหลดไฟล์แนบ ->
    เตรียมแถว -> เขียนชีต -> ส่ง LINE
    รหัสรายงานต้องสร้างก่อนอัปโหลด เพราะชื่อโฟลเดอร์ไฟล์แนบใช้รหัสนี้
    """
    station_id = authorized_station(req.formData, session)
    record_id = generate_record_id(prefix)
    attachments = prepare_attachments(req.files, station_id, record_id, str(req.formData.get("unitId", "")))
    prepared = build(record_id, attachments["folderUrl"])
    return submit(prepared, attachments, message)


@app.post("/api/reports/daily-result")
def submit_daily_result(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """บันทึกผลการปฏิบัติประจำวัน (RST)"""
    return handle_submission(
        req, session, "RST",
        lambda rid, folder: prepare_daily_result(req.formData, charges=req.charges, folder_url=folder, record_id=rid),
        "บันทึกผลการปฏิบัติประจำวันเรียบร้อยแล้ว",
    )


@app.post("/api/reports/station-duty")
def submit_station_duty(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """บันทึกยอดเวรประจำสถานี (STD)"""
    return handle_submission(
        req, session, "STD",
        lambda rid, folder: prepare_station_duty(req.formData, folder_url=folder, record_id=rid),
        "บันทึกรายงานยอดเวรเรียบร้อยแล้ว",
    )


@app.post("/api/reports/other-duty")
def submit_other_duty(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """บันทึกภารกิจอื่น / จิตอาสา (OTH)"""
    return handle_submission(
        req, session, "OTH",
        lambda rid, folder: prepare_other_duty(req.formData, officers=req.officers, folder_url=folder, record_id=rid),
        "บันทึกรายงานการปฏิบัติเรียบร้อยแล้ว",
    )


@app.post("/api/reports/accident")
def submit_accident_report(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """บันทึกรายงานอุบัติเหตุ (ACC)"""
    return handle_submission(
        req, session, "ACC",
        lambda rid, folder: prepare_accident_report(req.formData, folder_url=folder, record_id=rid),
        "บันทึกรายงานอุบัติเหตุเรียบร้อยแล้ว",
    )


@app.post("/api/reports/mission")
def submit_mission_report(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """บันทึกการแจ้งภารกิจ (MIS)"""
    return handle_submission(
        req, session, "MIS",
        lambda rid, folder: prepare_mission_report(
            req.formData, selected_units=req.selectedUnits, folder_url=folder, record_id=rid
        ),
        "แจ้งภารกิจเรียบร้อยแล้ว",
    )


@app.post("/api/reports/royal-guard")
def submit_royal_guard_report(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """บันทึกรายงานถวายความปลอดภัย (RG)"""
    return handle_submission(
        req, session, "RG",
        lambda rid, folder: prepare_royal_guard_report(req.formData, folder_url=folder, record_id=rid),
        "บันทึกรายงานถวายความปลอดภัยเรียบร้อยแล้ว",
    )


@app.post("/api/reports/fuel")
def submit_fuel_record(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """บันทึกการเติมน้ำมัน / เปลี่ยนน้ำมันเครื่อง (FUEL)"""
    return handle_submission(
        req, session, "FUEL",
        lambda rid, folder: prepare_fuel_record(req.formData, record_id=rid, folder_url=folder),
        "บันทึกข้อมูลน้ำมันเรียบร้อยแล้ว",
    )


@app.post("/api/reports/document")
def submit_document_record(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """บันทึกเอกสารเข้าระบบสารบรรณ (DOC)"""
    return handle_submission(
        req, session, "DOC",
        lambda rid, folder: prepare_document_record(req.formData, folder_url=folder, record_id=rid),
        "ส่งเอกสารเข้าสู่ระบบเรียบร้อยแล้ว",
    )


@app.post("/api/reports/overweight")
def submit_overweight_report(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """
    รายงานการตรวจสอบรถบรรทุกน้ำหนักเกิน (OWT) — requirement ข้อ 8

    มาแทนเมนู "บันทึกข้อความ" ของผู้ปฏิบัติ แต่เขียนลงตารางใหม่ `tb_OverweightTrucks`
    ส่วน `/api/reports/document` ยังอยู่ เพราะเอกสารที่ส่งเข้าระบบสารบรรณไปแล้วต้อง
    เปิดดูย้อนหลังได้ และงานสารบรรณเป็นคนละเรื่องกับการตรวจน้ำหนักรถ
    """
    return handle_submission(
        req, session, "OWT",
        lambda rid, folder: prepare_overweight_report(req.formData, folder_url=folder, record_id=rid),
        "บันทึกรายงานตรวจรถบรรทุกน้ำหนักเกินเรียบร้อยแล้ว",
    )


# ------------------------------------------------------- โมดูลประชาสัมพันธ์ (ข้อ 13)

# สิทธิ์อนุมัติข่าวและจัดการคำค้น (FR-09) — ชุดเดียวกับที่อนุมัติรายงานอื่นระดับสถานีขึ้นไป
PR_ADMIN_ROLES = {
    "สิบเวร", "Station_Admin", "Division_Admin", "Division_Commander",
    "HQ_Admin", "Super_Commander",
    # ฝ่ายประชาสัมพันธ์ทำงานนี้เต็มวงจร แต่แตะอย่างอื่นในระบบไม่ได้เลย
    # ดู PR_ONLY_ALLOWED_PREFIXES ซึ่งเป็นด่านที่บังคับข้อจำกัดนั้นจริง ๆ
    *PR_ONLY_ROLES,
}


def _require_pr_admin(session: Dict[str, Any]) -> None:
    if str(session.get("r") or "") not in PR_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="เฉพาะแอดมินเท่านั้นที่จัดการงานประชาสัมพันธ์ได้")


@app.post("/api/pr/news")
def submit_pr_news(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """
    รับข่าวประชาสัมพันธ์จากผู้ปฏิบัติ (FR-01) พร้อมตรวจคุณภาพสื่อ (FR-02/BR-01)

    สื่อที่ต่ำกว่า 1080p **ไม่ทำให้ข่าวถูกปฏิเสธ** แต่ทำให้ข่าวติดธงรอพิจารณา
    การทิ้งงานของเจ้าหน้าที่เพราะภาพความละเอียดต่ำจะทำให้ไม่มีใครส่งข่าวเข้าระบบ
    """
    station_id = authorized_station(req.formData, session)
    record_id = generate_record_id("PR")
    attachments = prepare_attachments(req.files, station_id, record_id, str(req.formData.get("unitId", "")))

    # ค่าที่เบราว์เซอร์วัดมาส่งใน formData.mediaMeta ส่วนเนื้อไฟล์อยู่ใน req.files
    # จับคู่ตามลำดับเดียวกันเพราะทั้งสองชุดสร้างจาก FileList ตัวเดียวกัน
    meta = req.formData.get("mediaMeta")
    meta_list = meta if isinstance(meta, list) else []
    merged: List[Dict[str, Any]] = []
    for index, item in enumerate(meta_list):
        entry = dict(item) if isinstance(item, dict) else {}
        raw_file = (req.files or [])[index] if index < len(req.files or []) else None
        if raw_file:
            try:
                _, content = parse_data_url(str(raw_file.get("data") or ""))
                entry["_bytes"] = content
            except AttachmentError:
                entry["_bytes"] = b""
        entry.setdefault("url", attachments.get("folderUrl", ""))
        merged.append(entry)

    media = pr_service.evaluate_media(merged)
    matched = pr_service.match_keywords(
        f"{req.formData.get('title', '')} {req.formData.get('content', '')}"
    )

    try:
        prepared = pr_service.prepare_news(
            req.formData, media, matched, folder_url=attachments["folderUrl"], record_id=record_id
        )
    except pr_service.PRError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = submit(prepared, attachments, "ส่งข่าวประชาสัมพันธ์เข้าคิวตรวจแล้ว")

    # แถวสื่อเขียนหลังข่าวเสมอ ถ้าเขียนก่อนแล้วข่าวเขียนไม่สำเร็จ จะเหลือแถวสื่อลอย
    # ที่ไม่มีข่าวต้นทาง ซึ่งตามกลับไม่ได้ว่าเป็นของใคร
    if media:
        try:
            sheets_service.append_report_rows(
                prepared["targetDbId"],
                pr_service.MEDIA_TABLE,
                pr_service.prepare_media_rows(record_id, req.formData, media),
            )
        except SheetWriteError as exc:
            logger.error("บันทึกข้อมูลสื่อของข่าว %s ไม่สำเร็จ: %s", record_id, exc)

    audit_service.record(
        session, audit_service.ACTION_CREATE, pr_service.NEWS_TABLE, record_id,
        after={"หัวข้อข่าว": req.formData.get("title", ""), "แหล่งที่มา": req.formData.get("source", "internal")},
        note=f"สื่อ {len(media)} ไฟล์ ผ่านเกณฑ์ {sum(1 for m in media if m['passed'])} ไฟล์",
        station_id=station_id,
    )

    result["media"] = [{k: v for k, v in m.items() if k != "_bytes"} for m in media]
    result["needsMediaReview"] = prepared["needsMediaReview"]
    result["matchedKeywords"] = matched
    return result


@app.get("/api/pr/news")
def list_pr_news(
    station: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    source: Optional[str] = None,
    newsType: Optional[str] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    needsReview: bool = False,
    session: Dict[str, Any] = Depends(current_session),
):
    """ตารางรวมข่าวทุกแหล่ง พร้อมตัวกรองและยอดสรุป (FR-04)"""
    station_id = authorized_station_for_stats(station, session)
    try:
        items = pr_service.list_news(
            station_id,
            start=start or "", end=end or "", source=source or "",
            news_type=newsType or "", keyword=keyword or "", status=status or "",
            only_needs_review=needsReview,
        )
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"status": "success", "data": {"items": items, "summary": pr_service.summarize(items)}}


@app.get("/api/pr/news/media")
def pr_news_media(
    recordId: str,
    station: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """ไฟล์สื่อของข่าวหนึ่งใบ ใช้ในหน้าตรวจก่อนอนุมัติ"""
    station_id = authorized_station_for_stats(station, session)
    try:
        return {"status": "success", "data": pr_service.media_of(station_id, recordId)}
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/pr/news/decide")
def decide_pr_news(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """
    อนุมัติหรือปฏิเสธข่าว (FR-09) — เฉพาะแอดมิน

    ปฏิเสธใช้ soft delete ตาม FR-05 (Sys_Status = Canceled, Sys_IsActive = FALSE)
    แถวยังอยู่ในชีตครบ ไม่มีเส้นทางไหนในระบบที่ลบแถวข่าวออกจริง
    """
    _require_pr_admin(session)

    record_id = str(payload.get("recordId") or "").strip()
    approve = bool(payload.get("approve"))
    note = str(payload.get("note") or "").strip()

    if not approve and not note:
        raise HTTPException(status_code=400, detail="การปฏิเสธข่าวต้องระบุเหตุผล")

    record = _pr_news_for_admin(record_id, session, payload.get("station"))
    before = record.get(query_service.COL_STATUS, "")
    status = query_service.STATUS_APPROVED if approve else query_service.STATUS_CANCELED

    try:
        query_service.set_status(record, pr_service.NEWS_TABLE, status, approve)
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    audit_service.record(
        session,
        audit_service.ACTION_APPROVE if approve else audit_service.ACTION_REJECT,
        pr_service.NEWS_TABLE, record_id,
        before={query_service.COL_STATUS: before},
        after={query_service.COL_STATUS: status},
        note=note,
        station_id=record.get(query_service.COL_STATION_ID),
    )
    return {"status": "success", "message": "อนุมัติข่าวแล้ว" if approve else "ปฏิเสธข่าวแล้ว"}


def _pr_news_for_admin(
    record_id: str,
    session: Dict[str, Any],
    station: Optional[str] = None,
) -> Dict[str, Any]:
    """
    หาแถวข่าวที่แอดมินคนนี้มีสิทธิ์จัดการ ใช้ร่วมกันทุกเส้นทางที่แตะข่าวรายใบ

    **ต้องรับรหัสสถานีจากหน้าเว็บ ไม่ใช่ยึดจาก session อย่างเดียว** แอดมินส่วนกลาง
    อยู่สถานี "00" ซึ่งไม่ใช่ กก. ไหนเลย การเอา "00" ไปหาสเปรดชีตจึงล้มพร้อมข้อความ
    "กองกำกับการ 0 ยังไม่ได้ตั้งค่าฐานข้อมูล" ที่ทั้งผิดและตามหาต้นเหตุไม่เจอ

    ใช้ `authorized_station_id` ไม่ใช่ `authorized_station_for_stats` เพราะสามเส้นทาง
    ที่เรียกตัวนี้เป็นการ**เขียน** ตัวหลังปล่อยให้ ผกก. ข้ามกองได้ซึ่งจะทำให้ ผกก. กก.5
    อนุมัติและแจกลิงก์ข่าวของ กก.1 ได้ ตรงข้ามกับ requirement ข้อ 1 พอดี
    """
    if not str(record_id or "").strip():
        raise HTTPException(status_code=400, detail="ไม่พบรหัสข่าว")

    station_id = authorized_station_id(station, session)
    try:
        record = query_service.find_record(station_id, pr_service.NEWS_TABLE, record_id.strip())
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not check_station_match(station_id, record.get(query_service.COL_STATION_ID, "")):
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์จัดการข่าวของสถานีอื่น")
    return record


@app.get("/api/pr/divisions")
def pr_divisions(session: Dict[str, Any] = Depends(current_session)):
    """
    รายชื่อ กก. ที่ฝ่ายประชาสัมพันธ์เลือกทำงานด้วยได้

    ฝ่าย PR อยู่ระดับ บก. สถานี "00" ซึ่งไม่ใช่ กก. ไหน หน้าจอจึงต้องให้เลือกกองก่อน
    ไม่งั้นทุกคำขอจะไม่รู้ว่าต้องเปิดสเปรดชีตของใคร

    ซ้ำกับ `/api/commander/divisions` โดยตั้งใจ ตัวนั้นอยู่ใต้ `CROSS_DIVISION_VIEW_ROLES`
    ซึ่งเป็นชุดสิทธิ์ของฝ่ายบังคับบัญชา การยัดฝ่าย PR เข้าไปในชุดนั้นเพื่อให้ได้แค่รายชื่อ
    กองจะพ่วงสิทธิ์อ่านสถิติข้ามกองไปด้วยทั้งชุด ซึ่งกว้างกว่าที่งานนี้ต้องใช้มาก

    คืนเฉพาะกองที่ตั้งค่าฐานข้อมูลไว้แล้ว การโชว์กองที่ยังไม่มีฐานข้อมูลคือพาผู้ใช้ไปเจอ error
    """
    return {
        "status": "success",
        "data": [
            {"division": division, "name": f"กก.{division}", "station": f"{division}0"}
            for division, entry in sorted(get_db_router().items())
            if division != "0" and entry.get("OPS")
        ],
    }


@app.get("/api/pr/templates")
def pr_templates(session: Dict[str, Any] = Depends(current_session)):
    """เทมเพลตชิ้นงาน PR ที่มีให้เลือก (FR-07)"""
    return {
        "status": "success",
        "data": [{"key": key, "label": label} for key, label in pr_service.PR_TEMPLATES.items()],
    }


@app.post("/api/pr/news/compose")
def compose_pr_news(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """
    ประกอบชิ้นงาน PR ตามเทมเพลตแล้วคืนข้อความ ยังไม่แตะ Drive (FR-07)

    แยกจากขั้นสร้างลิงก์เพราะเจ้าหน้าที่ต้องได้อ่านก่อนว่าจะแจกอะไรออกไป การอัปไฟล์
    แล้วเปิดสาธารณะทันทีตั้งแต่กดปุ่มแรกทำให้ทุกครั้งที่ลองดูเฉย ๆ กลายเป็นการเผยแพร่จริง
    """
    _require_pr_admin(session)

    record = _pr_news_for_admin(str(payload.get("recordId") or ""), session, payload.get("station"))
    template = str(payload.get("template") or pr_service.DEFAULT_TEMPLATE)
    item = pr_service.news_item(record)

    try:
        content = pr_service.compose(item, template)
    except pr_service.PRError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "success",
        "data": {
            "recordId": item["recordId"],
            "template": template,
            "templateLabel": pr_service.PR_TEMPLATES.get(template, template),
            "content": content,
            "shareUrl": item["shareUrl"],
        },
    }


@app.post("/api/pr/news/share")
def share_pr_news(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """
    อัปชิ้นงาน PR ขึ้น Drive แล้วคืนลิงก์สาธารณะ (FR-08)

    **เฉพาะข่าวที่อนุมัติแล้ว** ลิงก์นี้ใครถือก็เปิดได้โดยไม่ต้องล็อกอิน ข่าวที่ยังรอ
    ตรวจหรือถูกปฏิเสธไปแล้วจึงต้องแจกไม่ได้ ไม่งั้นคิวอนุมัติของ FR-09 ก็ข้ามได้
    ด้วยการกดปุ่มแชร์แทน

    สิทธิ์ที่ให้คือ reader และให้ที่ตัวไฟล์ชิ้นงานเท่านั้น ไม่ใช่ที่โฟลเดอร์ไฟล์แนบ
    ซึ่งมีภาพจากที่เกิดเหตุปนอยู่ (ดู `storage_service.PUBLIC_PERMISSION`)
    """
    _require_pr_admin(session)

    record = _pr_news_for_admin(str(payload.get("recordId") or ""), session, payload.get("station"))
    item = pr_service.news_item(record)

    if item["status"] != query_service.STATUS_APPROVED:
        raise HTTPException(
            status_code=409,
            detail=f"สร้างลิงก์สาธารณะได้เฉพาะข่าวที่อนุมัติแล้ว (สถานะปัจจุบัน: {item['status'] or 'ไม่ทราบ'})",
        )

    template = str(payload.get("template") or pr_service.DEFAULT_TEMPLATE)
    try:
        content = pr_service.compose(item, template)
    except pr_service.PRError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    station_id = str(record.get(query_service.COL_STATION_ID, "") or session.get("s") or "")
    uploaded = storage_service.store_public_text(
        content,
        pr_service.artifact_filename(item["recordId"], template),
        station_id,
    )
    if not uploaded["stored"]:
        raise HTTPException(status_code=502, detail=uploaded["warning"])

    # ลำดับสามขั้นนี้สลับกันไม่ได้ — อัป, บันทึกลงชีต, แล้วค่อยถอนของเก่า
    #
    # ไฟล์ที่เปิดสาธารณะแล้วแต่รหัสไม่ได้ลงชีต คือไฟล์ที่กดถอนจากหน้าเว็บไม่ได้อีกเลย
    # เพราะไม่มีใครรู้ว่ามันอยู่ที่ไหน ถ้าเขียนชีตพลาดจึงต้องถอนตัวที่เพิ่งอัปทิ้งทันที
    # แล้วปล่อยให้ลิงก์เดิม (ที่ชีตยังชี้อยู่) ทำงานต่อ ระบบจะได้กลับไปอยู่สภาพเดิมทั้งใบ
    now = datetime.now().isoformat()
    try:
        query_service.write_columns(
            record,
            pr_service.NEWS_TABLE,
            {
                "เทมเพลตชิ้นงาน PR": template,
                "Share_File_ID": uploaded["fileId"],
                "Share_Url": uploaded["url"],
                "วันเวลาที่สร้างลิงก์": now,
            },
        )
    except SheetWriteError as exc:
        storage_service.revoke_public_link(uploaded["fileId"])
        logger.error("บันทึกลิงก์ของ %s ลงชีตไม่สำเร็จ ถอนไฟล์ที่เพิ่งอัปแล้ว: %s", item["recordId"], exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # ชีตชี้ไปที่ไฟล์ใหม่แล้ว ของเก่าจึงตามไปปิดได้ปลอดภัย ถ้าถอนตั้งแต่ก่อนเขียนชีต
    # แล้วเขียนพลาด ข่าวใบนี้จะเหลือลิงก์ที่ตายแล้วหนึ่งอันกับลิงก์ที่ตามไม่ได้อีกหนึ่งอัน
    previous_id = str(item["shareFileId"] or "").strip()
    if previous_id and previous_id != uploaded["fileId"]:
        storage_service.revoke_public_link(previous_id)

    audit_service.record(
        session, audit_service.ACTION_PUBLISH, pr_service.NEWS_TABLE, item["recordId"],
        before={"Share_Url": item["shareUrl"]},
        after={"Share_Url": uploaded["url"], "เทมเพลตชิ้นงาน PR": template},
        note=f'สร้างลิงก์สาธารณะแบบ "{pr_service.PR_TEMPLATES.get(template, template)}"',
        station_id=record.get(query_service.COL_STATION_ID),
    )

    return {
        "status": "success",
        "message": "สร้างลิงก์สาธารณะแล้ว ทุกคนที่มีลิงก์เปิดอ่านได้ แต่แก้ไขไม่ได้",
        "data": {
            "recordId": item["recordId"],
            "template": template,
            "templateLabel": pr_service.PR_TEMPLATES.get(template, template),
            "content": content,
            "shareUrl": uploaded["url"],
            "shareFileId": uploaded["fileId"],
            "sharedAt": now,
        },
    }


@app.post("/api/pr/news/share/revoke")
def revoke_pr_news_share(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """
    ถอนลิงก์สาธารณะของชิ้นงาน PR (FR-08)

    ต้องมีทางปิดที่กดได้จากหน้าเว็บ ไม่ใช่ต้องเข้า Drive ไปไล่หาไฟล์เอง ลิงก์ที่แจกผิด
    แล้วปิดไม่เป็นคือลิงก์ที่เปิดค้างตลอดไป ตัวไฟล์ไม่ถูกลบ เพื่อให้ตามย้อนได้ว่าเคยแจกอะไร
    """
    _require_pr_admin(session)

    record = _pr_news_for_admin(str(payload.get("recordId") or ""), session, payload.get("station"))
    item = pr_service.news_item(record)

    file_id = str(item["shareFileId"] or "").strip()
    if not file_id:
        raise HTTPException(status_code=404, detail="ข่าวใบนี้ยังไม่มีลิงก์สาธารณะให้ถอน")

    result = storage_service.revoke_public_link(file_id)
    if not result["revoked"]:
        raise HTTPException(status_code=502, detail=result["warning"])

    try:
        query_service.write_columns(
            record,
            pr_service.NEWS_TABLE,
            {"Share_File_ID": "", "Share_Url": "", "วันเวลาที่สร้างลิงก์": ""},
        )
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    audit_service.record(
        session, audit_service.ACTION_UPDATE, pr_service.NEWS_TABLE, item["recordId"],
        before={"Share_Url": item["shareUrl"]}, after={"Share_Url": ""},
        note="ถอนลิงก์สาธารณะของชิ้นงาน PR",
        station_id=record.get(query_service.COL_STATION_ID),
    )
    return {"status": "success", "message": "ถอนลิงก์สาธารณะแล้ว ลิงก์เดิมเปิดไม่ได้อีก"}


@app.get("/api/pr/report/pending")
def pr_pending_report(
    station: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """
    รายงานข่าวค้างอนุมัติแยกตามสังกัด (FR-10) — เฉพาะแอดมิน ชุดเดียวกับที่อนุมัติข่าวได้

    เป็นรายงานสำหรับคนที่ต้องไปตามข่าวค้าง ไม่ใช่ตัวเลขสาธารณะ ผู้ปฏิบัติเห็นคิว
    ของตัวเองผ่านหน้าประวัติการส่งอยู่แล้ว
    """
    _require_pr_admin(session)
    station_id = authorized_station_for_stats(station, session)
    try:
        return {
            "status": "success",
            "data": pr_service.pending_report(station_id, start=start or "", end=end or ""),
        }
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/pr/keywords")
def list_pr_keywords(session: Dict[str, Any] = Depends(current_session)):
    """คำค้นที่ใช้กรองข่าว (FR-02) ผู้ปฏิบัติดูได้ แต่แก้ไม่ได้"""
    try:
        return {"status": "success", "data": pr_service.get_keywords(active_only=False)}
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/pr/keywords")
def save_pr_keyword(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """เพิ่มหรือแก้คำค้น (FR-09) — เฉพาะแอดมิน"""
    _require_pr_admin(session)

    keyword = str(payload.get("keyword") or "").strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="กรุณาระบุคำค้น")

    row = [
        keyword,
        str(payload.get("category") or "").strip(),
        str(payload.get("note") or "").strip(),
        "FALSE" if payload.get("isActive") is False else "TRUE",
        datetime.now().isoformat(),
        str(session.get("u") or ""),
    ]

    try:
        sheets_service.append_report_row(MASTER_SHEET_ID, pr_service.KEYWORDS_TABLE, row)
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    query_service.invalidate_cache(MASTER_SHEET_ID, pr_service.KEYWORDS_TABLE)
    audit_service.record(
        session, audit_service.ACTION_CREATE, pr_service.KEYWORDS_TABLE, keyword,
        after={"Keyword": keyword}, note="แอดมินเพิ่มคำค้น",
    )
    return {"status": "success", "message": f'เพิ่มคำค้น "{keyword}" แล้ว'}


@app.get("/api/health/database")
def database_health(session: Dict[str, Any] = Depends(current_session)):
    """
    ตรวจว่าฐานข้อมูลของแต่ละ กก. ต่อติดจริงหรือไม่ ใช้ยืนยันว่าข้อมูลไหลไปถูกที่
    คืนสถานะรายกองกำกับ พร้อมรายชื่อแท็บที่มีอยู่จริงในสเปรดชีตนั้น

    จำกัดที่ระดับส่วนกลาง เพราะสิ่งที่ตอบกลับคือผังฐานข้อมูลทั้งระบบ — รหัสสเปรดชีต
    ของทุกกอง อีเมลบัญชีบริการ และชื่อแท็บทั้งหมด ผู้ปฏิบัติหนึ่งคนไม่มีเหตุต้องรู้
    หน้าเดียวที่เรียก endpoint นี้คือหน้าผู้บังคับการอยู่แล้ว
    """
    _require_hq(session)
    configured = sheets_service.is_configured()
    report: Dict[str, Any] = {
        "credentialsConfigured": configured,
        "authMode": sheets_service.auth_mode(),
        "serviceAccountEmail": sheets_service.service_account_email(),
        "expectedTables": sorted(TABLE_COLUMNS),
        "divisions": [],
    }

    for division, entry in sorted(get_db_router().items()):
        sheet_id = (entry or {}).get("OPS", "")
        row: Dict[str, Any] = {"division": division, "spreadsheetId": sheet_id, "status": "not_configured"}

        if sheet_id and configured:
            try:
                spreadsheet = sheets_service.open_spreadsheet(sheet_id)
                existing = [ws.title for ws in spreadsheet.worksheets()]
                row.update(
                    status="ok",
                    title=spreadsheet.title,
                    tabs=existing,
                    missingTables=[
                        t for t in sorted(TABLE_COLUMNS)
                        if t not in existing and t not in MASTER_ONLY_TABLES
                    ],
                )
            except (SheetNotConfigured, SheetWriteError) as exc:
                row.update(status="error", message=str(exc))
            except Exception as exc:  # noqa: BLE001
                # gspread โยน SpreadsheetNotFound / APIError ตรง ๆ ไม่ผ่าน error ของเรา
                # ปล่อยให้หลุดขึ้นไปจะทำให้หน้าตรวจสุขภาพพังทั้งหน้า ทั้งที่มันมีไว้บอก
                # ว่ากองไหนเปิดไม่ได้ ยิ่งกองเดียวเสียยิ่งต้องเห็นอีกเจ็ดกองที่ยังดีอยู่
                logger.warning("เปิดสเปรดชีตของ กก.%s ไม่สำเร็จ: %s", division, exc)
                row.update(status="error", message=f"{type(exc).__name__}: {exc}")
        elif sheet_id:
            row["status"] = "credentials_missing"

        report["divisions"].append(row)

    return report


# ==========================================================================
# หน้า ฝอ.กก. และหน้าผู้กำกับการ
#
# ทั้งชุดจำกัดที่ DIVISION_VIEW_ROLES เป็นอย่างต่ำ และทุก endpoint บังคับสถานีผ่าน
# authorized_station_id เสมอ ผู้กำกับการ กก.5 จึงยิงขอข้อมูล กก.3 ไม่ได้แม้แก้ URL
# ==========================================================================


def _require_division(session: Dict[str, Any]) -> None:
    if str(session.get("r") or "") not in DIVISION_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ดูข้อมูลระดับกองกำกับการ")


def _require_division_admin(session: Dict[str, Any]) -> None:
    """
    งานธุรการในหน้า ฝอ.กก. — ตั้งโควตาน้ำมัน แก้สถานะกำลังพล จัดหมวดของกลาง นำขบวน

    ผู้กำกับการรวมอยู่ด้วย เพราะ cmdSwitchToHQ ของเดิมเปิด hqDashboard ตัวเดียวกัน
    กับที่ ฝอ. ใช้ โดยไม่เช็ค role เลยสักจุด (ทั้งไฟล์ hq_dashboard.html มีคำว่า role
    อยู่ที่เดียวคือ role="group" ของ Bootstrap) ผกก. จึงได้ปุ่มบันทึกครบเหมือนกัน

    ที่กันออกคือระดับสถานีกับผู้ปฏิบัติ ซึ่งเข้าหน้านี้ไม่ได้ตั้งแต่ต้นอยู่แล้ว
    """
    allowed = {"Division_Admin", "Division_Commander", "HQ_Admin", "Super_Commander"}
    if str(session.get("r") or "") not in allowed:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์แก้ไขข้อมูลระดับกองกำกับการ")


def _current_month() -> str:
    return datetime.now().strftime("%Y-%m")


@app.get("/api/hq/fuel")
def hq_fuel(
    station: Optional[str] = None,
    month: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """โควตากับยอดใช้น้ำมันรายสถานีของเดือนที่เลือก พร้อมรายการเบิกทีละใบ"""
    station_id = authorized_station_id(station, session)
    _require_division(session)
    try:
        data = hq_service.fuel_summary(station_id, month or _current_month())
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@app.post("/api/hq/fuel/quota")
def hq_fuel_quota(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """ตั้งโควตาน้ำมันประจำเดือนให้ทุกสถานีใน กก. พร้อมกัน"""
    station_id = authorized_station_id(payload.get("stationId"), session)
    _require_division_admin(session)
    month = str(payload.get("monthYear") or "").strip() or _current_month()
    quotas = payload.get("quotas") or []
    if not isinstance(quotas, list):
        raise HTTPException(status_code=400, detail="quotas ต้องเป็นรายการ")
    try:
        saved = hq_service.save_fuel_quota(station_id, month, quotas, str(session.get("u") or ""))
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "message": f"บันทึกโควตาน้ำมันเดือน {month} แล้ว {saved} สถานี"}


@app.get("/api/hq/manpower")
def hq_manpower(station: Optional[str] = None, session: Dict[str, Any] = Depends(current_session)):
    """ยอดกำลังพลรายสถานีทั้ง กก. คู่กับผังกำลังพลของสถานีที่ระบุ"""
    station_id = authorized_station_id(station, session)
    _require_division(session)
    try:
        return {
            "status": "success",
            "data": {
                "overview": hq_service.manpower_overview(station_id),
                "station": hq_service.manpower_data(station_id),
            },
        }
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/hq/manpower/status")
def hq_manpower_status(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """ตั้งหรือยกเลิกสถานะไปช่วยราชการของเจ้าหน้าที่หนึ่งคน"""
    _require_division_admin(session)
    username = str(payload.get("username") or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="ไม่พบชื่อผู้ใช้ที่ต้องการแก้ไข")
    try:
        name = hq_service.update_manpower_status(
            username,
            str(payload.get("helpStationId") or ""),
            str(payload.get("startDate") or ""),
            str(payload.get("endDate") or ""),
            str(payload.get("remark") or ""),
            # tb_Users อยู่ในชีตกลางร่วมกันทั้ง 8 กก. ถ้าไม่ส่งขอบเขตลงไป ฝอ.กก.5
            # จะแก้สถานะของเจ้าหน้าที่ใน กก.1 ได้ ซึ่งเป็นช่องที่ requirement ข้อ 1
            # สั่งให้ปิด
            allowed_station=str(session.get("s") or ""),
        )
    except hq_service.OutOfScope as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "message": f"อัปเดตสถานะกำลังพลของ {name} แล้ว"}


@app.get("/api/hq/evidence")
def hq_evidence(
    station: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """คดีจับกุมที่อนุมัติแล้ว พร้อมสถานะว่าจัดหมวดหมู่ของกลางแล้วหรือยัง"""
    station_id = authorized_station_id(station, session)
    _require_division(session)
    try:
        data = hq_service.evidence_list(station_id, start or "", end or "")
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@app.post("/api/hq/evidence")
def hq_evidence_save(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """บันทึกของกลางที่จัดหมวดหมู่แล้วกลับลงคดี"""
    station_id = authorized_station_id(payload.get("stationId"), session)
    _require_division_admin(session)
    record_id = str(payload.get("recordId") or "").strip()
    if not record_id:
        raise HTTPException(status_code=400, detail="ไม่พบรหัสคดีที่ต้องการอัปเดต")
    try:
        hq_service.save_evidence(station_id, record_id, payload.get("items"))
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "message": "จัดหมวดหมู่ของกลางเรียบร้อยแล้ว"}


@app.get("/api/hq/escort")
def hq_escort(
    station: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """งานนำขบวนในช่วงวันที่ พร้อมยอดแยกบุคคลสำคัญกับทั่วไป"""
    station_id = authorized_station_for_stats(station, session)
    _require_division(session)
    try:
        data = hq_service.escort_data(station_id, start or "", end or "")
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@app.post("/api/hq/escort")
def hq_escort_save(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """บันทึกงานนำขบวนที่ส่วนกลางมอบหมายให้ กก."""
    station_id = authorized_station_id(payload.get("stationId"), session)
    _require_division_admin(session)
    start_at = str(payload.get("startDateTime") or "").strip()
    if not start_at:
        raise HTTPException(status_code=400, detail="กรุณาระบุวันเวลาเริ่มนำขบวน")

    files = payload.get("files")
    record_id = f"ESC-{station_id}-{datetime.now().strftime('%y%m%d-%H%M%S')}"
    attachments = prepare_attachments(files, station_id, record_id, "นำขบวน") if files else {}

    try:
        hq_service.save_escort(
            station_id,
            str(payload.get("escortType") or ""),
            start_at,
            str(payload.get("endDateTime") or ""),
            str(payload.get("details") or ""),
            str(session.get("u") or ""),
            attachments.get("folderUrl", ""),
        )
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "message": "บันทึกข้อมูลการนำขบวนเรียบร้อยแล้ว"}


@app.get("/api/hq/daily-detail")
def hq_daily_detail(
    station: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """ทุกรายงานที่อนุมัติแล้วในช่วงวันที่ เรียงตามเวลา สำหรับหน้ารายละเอียดรายวัน"""
    station_id = authorized_station_for_stats(station, session)
    _require_division(session)
    try:
        data = hq_service.daily_detail(station_id, start or "", end or "")
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@app.get("/api/commander/overview")
def commander_overview(
    station: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """
    ผลงานรายสถานีคู่กับกำลังพลที่มีจริง และภารกิจเฉลี่ยต่อคน

    ติดธง `readOnly` กลับไปเมื่อกำลังดู กก. อื่น เพื่อให้หน้าเว็บซ่อนกล่องสั่งการ
    ธงนี้เป็นเรื่องของการบอกผู้ใช้ ไม่ใช่กลไกความปลอดภัย ตัวที่กันจริงคือ 403 ที่
    `/api/commander/order` และเส้นทางเขียนทุกเส้น
    """
    station_id = authorized_station_for_stats(station, session)
    _require_division(session)
    try:
        data = hq_service.executive_overview(station_id, start or "", end or "")
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    data["readOnly"] = is_viewing_other_division(station_id, session)
    return {"status": "success", "data": data}


@app.get("/api/commander/divisions")
def commander_divisions(session: Dict[str, Any] = Depends(current_session)):
    """
    รายชื่อ กก. ที่บัญชีนี้เปิดดูสถิติได้ พร้อมธงว่าเป็นกองของตัวเองหรือไม่ (ข้อ 1)

    คืนเฉพาะ กก. ที่ตั้งค่าฐานข้อมูลไว้แล้ว การโชว์กองที่ยังไม่มีฐานข้อมูลคือพาผู้ใช้
    ไปเจอ error ไม่ใช่พาไปดูข้อมูล
    """
    if str(session.get("r") or "") not in CROSS_DIVISION_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ดูข้อมูลข้ามกองกำกับการ")

    own_division = str(session.get("s") or "")[:1]
    divisions = [
        {
            "division": division,
            "name": f"กก.{division}",
            # สถานีฝ่ายอำนวยการของกองนั้น ใช้เป็น station ที่ส่งกลับมาใน query
            "station": f"{division}0",
            "isOwn": division == own_division,
        }
        for division, entry in sorted(get_db_router().items())
        if division != "0" and entry.get("OPS")
    ]
    return {"status": "success", "data": divisions}


@app.get("/api/commander/calendar")
def commander_calendar(
    station: Optional[str] = None,
    month: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """ภารกิจที่ยังใช้งานอยู่ของเดือนนั้น สำหรับปฏิทินหน้าผู้กำกับการ"""
    station_id = authorized_station_for_stats(station, session)
    _require_division(session)
    try:
        data = hq_service.mission_calendar(station_id, month or _current_month())
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@app.post("/api/commander/order")
def commander_order(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """
    ส่งข้อความสั่งการเข้ากลุ่ม LINE ของสถานีในกองกำกับการตัวเอง

    ยึดกองกำกับการจาก session ไม่ใช่จาก payload — ไม่งั้นแก้ค่าใน request ก็สั่งการ
    ข้ามกองได้ ตรงตามที่ sendCommanderOrder ของเดิมเช็คไว้ (รหัส.js บรรทัด 3990)
    """
    if str(session.get("r") or "") not in {"Division_Commander", "Super_Commander"}:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์สั่งการ (เฉพาะระดับผู้บังคับบัญชา)")

    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="กรุณาพิมพ์ข้อความก่อนส่ง")

    own_station = str(session.get("s") or "").strip()
    allowed = set(get_division_stations(own_station, include_hq=True)) | {"00"}
    target = str(payload.get("target") or "ALL").strip()

    if target == "ALL":
        targets = sorted(allowed)
    elif target in allowed:
        targets = [target]
    else:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ส่งคำสั่งไปยังสถานีนอกกองกำกับการของท่าน")

    stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    commander = str(payload.get("commanderName") or session.get("u") or "")
    text = (
        f"📢 [ข้อความสั่งการจากผู้บังคับบัญชา]\n"
        f"วันที่: {stamp}\n"
        f"ผู้สั่งการ: {commander}\n\n"
        f'"{message}"\n\n'
        f"📌 โปรดรับทราบและปฏิบัติตามโดยเคร่งครัด"
    )

    # นับผลรายสถานี สถานีที่ยังไม่ได้ผูกกลุ่ม LINE จะถูกข้ามและรายงานกลับไปตามจริง
    # ไม่ใช่ตอบ success รวม ๆ ทั้งที่ไม่มีใครได้รับข้อความ
    sent, skipped = [], []
    for station_id in targets:
        group_id = get_station_data(station_id).get("lineGroupId", "")
        if not group_id:
            skipped.append(station_id)
            continue
        result = push_line_message(text, group_id)
        (sent if result.get("status") == "success" else skipped).append(station_id)

    if not sent:
        # บอกให้ครบว่าสถานีไหนบ้างและแก้ที่ไหน — ตอนเปิดใช้ทั้ง 8 กก. ยังไม่มีสถานีไหน
        # ผูกกลุ่ม LINE เลย ผู้บังคับบัญชาทุกกองจะเจอข้อความนี้เป็นด่านแรก ถ้าเขียนแค่
        # "ส่งไม่สำเร็จ" จะอ่านเหมือนระบบพัง แล้วโทรตามผู้ดูแลโดยไม่มีข้อมูลอะไรติดมือ
        names = ", ".join(skipped[:8]) + (" ..." if len(skipped) > 8 else "")
        raise HTTPException(
            status_code=502,
            detail=(
                f"ยังไม่ได้ผูกกลุ่ม LINE ของสถานีปลายทาง จึงยังส่งคำสั่งไม่ได้ "
                f"({len(skipped)} สถานี: {names}) "
                "ผู้ดูแลระบบต้องใส่ lineGroupId ของแต่ละสถานีใน STATION_SECRETS_JSON ก่อน "
                "ระหว่างนี้รายงานและงานอื่นยังใช้ได้ตามปกติ"
            ),
        )

    # requirement ข้อ 2 — คืนเบอร์ติดต่อของหัวหน้าหน่วยที่ได้รับคำสั่ง ให้ผู้สั่งการ
    # โทรตามได้ทันทีโดยไม่ต้องไปเปิดทำเนียบกำลังพลอีกหน้า
    #
    # เฉพาะสถานีที่ส่งสำเร็จจริง สถานีที่ถูกข้ามเพราะไม่มีกลุ่ม LINE ไม่ได้รับคำสั่ง
    # การให้เบอร์ของหน่วยนั้นมาด้วยจะทำให้เข้าใจผิดว่าสั่งไปแล้ว
    contacts: List[Dict[str, Any]] = []
    for station_id in sent:
        heads = user_service.station_heads(station_id)
        contacts.append(
            {
                "station": station_id,
                "stationName": get_station_data(station_id).get("fullName", station_id),
                "heads": heads,
            }
        )

    note = f" (ข้าม {len(skipped)} สถานีที่ยังไม่ได้ผูกกลุ่ม LINE)" if skipped else ""
    return {
        "status": "success",
        "message": f"ส่งข้อความสั่งการแล้ว {len(sent)} สถานี{note}",
        "contacts": contacts,
    }


@app.get("/api/hq/analysis/categories")
def hq_analysis_categories(session: Dict[str, Any] = Depends(current_session)):
    """หมวดรายงานจับกุมที่ให้เลือกชำแหละ พร้อมค่าที่ติ๊กไว้ตั้งแต่เปิดหน้า"""
    _require_division(session)
    return {
        "status": "success",
        "data": [{"name": name, "checked": checked} for name, checked in hq_service.ARREST_CATEGORIES],
    }


@app.post("/api/hq/analysis")
def hq_analysis(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """
    ตารางแจกแจง "ข้อหา/หมวดจับกุม x สถานี"

    ใช้ POST เพราะรายการหมวดที่เลือกมีได้หลายสิบตัวและเป็นข้อความไทยยาว ๆ ยัดลง
    query string แล้วชน limit ความยาว URL ของ proxy บางตัว
    """
    station_id = authorized_station_id(payload.get("stationId"), session)
    _require_division(session)

    mode = str(payload.get("mode") or "daily_charges")
    if mode not in {"daily_charges", "arrests"}:
        raise HTTPException(status_code=400, detail="โหมดวิเคราะห์ไม่ถูกต้อง")

    categories = payload.get("categories") or []
    if not isinstance(categories, list) or not categories:
        raise HTTPException(status_code=400, detail="กรุณาเลือกอย่างน้อยหนึ่งรายการ")

    try:
        data = hq_service.detailed_analysis(
            station_id,
            str(payload.get("start") or ""),
            str(payload.get("end") or ""),
            mode,
            [str(c) for c in categories],
        )
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@app.post("/api/hq/records")
def hq_records(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """ใบงานเบื้องหลังตัวเลขในตารางแจกแจง — เรียกตอนคลิกที่ตัวเลข"""
    station_id = authorized_station_id(payload.get("stationId"), session)
    _require_division(session)

    table = str(payload.get("sheetName") or "")
    if table not in {"tb_DailyResult", "tb_Arrests"}:
        raise HTTPException(status_code=400, detail="ตารางไม่ถูกต้อง")

    ids = payload.get("recordIds") or []
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="recordIds ต้องเป็นรายการ")

    try:
        data = hq_service.records_summary(station_id, table, [str(i) for i in ids])
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@app.post("/api/hq/comparison")
def hq_comparison(payload: Dict[str, Any], session: Dict[str, Any] = Depends(current_session)):
    """เทียบยอดของข้อหา/หมวดเดียวระหว่างสองช่วงเวลา แยกรายสถานี"""
    station_id = authorized_station_id(payload.get("stationId"), session)
    _require_division(session)

    mode = str(payload.get("mode") or "daily_charges")
    if mode not in {"daily_charges", "arrests"}:
        raise HTTPException(status_code=400, detail="โหมดวิเคราะห์ไม่ถูกต้อง")

    category = str(payload.get("category") or "").strip()
    if not category:
        raise HTTPException(status_code=400, detail="ไม่พบรายการที่ต้องการเปรียบเทียบ")

    raw = payload.get("ranges") or []
    ranges = [
        (str(r.get("start") or ""), str(r.get("end") or ""))
        for r in raw
        if isinstance(r, dict) and r.get("start") and r.get("end")
    ]
    if len(ranges) < 2:
        raise HTTPException(status_code=400, detail="กรุณาระบุช่วงวันที่ให้ครบทั้ง 2 ช่วง")

    try:
        data = hq_service.comparison_chart(station_id, ranges, mode, category)
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@app.get("/api/commander/summary")
def commander_summary(
    station: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """ตัวเลขทั้งหมดสำหรับประกอบรายงานสรุปส่งผู้บังคับบัญชา"""
    station_id = authorized_station_for_stats(station, session)
    _require_division(session)
    try:
        data = hq_service.commander_text_summary(station_id, start or "", end or "")
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}
