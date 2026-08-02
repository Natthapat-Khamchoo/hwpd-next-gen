"""
HWPD Next Gen - Python FastAPI Backend Entry Point
Exposes REST Endpoints matching the Google Apps Script RPC contracts.
"""

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
    check_station_match,
    get_db_router,
    get_session_secret,
    get_station_config,
    get_division_stations,
    get_station_data,
    get_target_db_id,
)
from app.core.schema import TABLE_COLUMNS
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
    prepare_fuel_record,
    prepare_mission_report,
    prepare_other_duty,
    prepare_royal_guard_report,
    prepare_station_duty,
)
from app.services import (
    docs_service,
    hq_service,
    national_service,
    query_service,
    reference_admin_service,
    reference_service,
    report_cache_service,
    report_export_service,
    search_service,
    sheets_service,
    user_service,
)
from app.services.docs_service import DocumentError, TemplateNotConfigured
from app.services.query_service import RecordNotFound
from app.services.reference_service import ReferenceDataUnavailable
from app.services.sheets_service import SheetNotConfigured, SheetWriteError, append_report_row
from app.services.user_service import UserDirectoryUnavailable
from app.services.storage_service import AttachmentError, store_attachments
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


@app.exception_handler(ValueError)
def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    """
    get_target_db_id ขว้าง ValueError เมื่อ กก. นั้นยังไม่ได้ตั้งค่าฐานข้อมูล
    ซึ่งเป็นเรื่องคอนฟิก ไม่ใช่ระบบพัง จึงตอบ 400 พร้อมข้อความไทยแทน 500
    """
    return JSONResponse(status_code=400, content={"status": "error", "message": str(exc)})


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


def current_session(x_token: Optional[str] = Header(None)) -> Dict[str, Any]:
    """ตรวจ Session Token ของทุก endpoint ที่เขียนข้อมูล"""
    session = verify_session_token(x_token or "")
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Session หมดอายุหรือไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่",
        )
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
    station_id = authorized_station_id(station, session)
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
    station_id = authorized_station_id(station, session)

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
    session: Dict[str, Any] = Depends(current_session),
):
    """
    ภาพรวมทั้งประเทศ อ่านจาก tb_National_Summary ที่งาน cron รวมยอดไว้แล้ว
    ไม่ได้อ่านชีตของ กก. สด ๆ เพราะ 8 กก. x 6 ตาราง ชนโควตาทันทีที่เปิดพร้อมกันสองคน
    """
    if str(session.get("r") or "") not in NATIONAL_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ดูภาพรวมระดับประเทศ")

    try:
        data = national_service.national_summary(start or "", end or "")
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

    return {"status": "success", "message": "ยกเลิกรายการนี้เรียบร้อยแล้ว"}


@app.post("/api/reports/daily")
def submit_daily_report(req: ReportSubmissionRequest, session: Dict[str, Any] = Depends(current_session)):
    """บันทึกรายงานประจำวัน (OP)"""
    station_id = authorized_station(req.formData, session)
    record_id = generate_record_id("OP")
    attachments = prepare_attachments(req.files, station_id, record_id, str(req.formData.get("unitId", "")))

    prepared = prepare_daily_report(req.formData, folder_url=attachments["folderUrl"], record_id=record_id)
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
    สร้างเอกสารจับกุมจากแม่แบบ Google Docs — ไม่เขียนลงตาราง คืนลิงก์ดาวน์โหลด

    รายการนี้ไม่ผูกกับสถานีในชีต จึงตรวจแค่ว่ามี session ที่ใช้ได้ ไม่ต้องมี stationId
    """
    if not req.suspectArray:
        raise HTTPException(status_code=400, detail="กรุณาระบุผู้ต้องหาอย่างน้อยหนึ่งคน")

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
        lambda rid, folder: prepare_fuel_record(req.formData, record_id=rid),
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


@app.get("/api/health/database")
def database_health(session: Dict[str, Any] = Depends(current_session)):
    """
    ตรวจว่าฐานข้อมูลของแต่ละ กก. ต่อติดจริงหรือไม่ ใช้ยืนยันว่าข้อมูลไหลไปถูกที่
    คืนสถานะรายกองกำกับ พร้อมรายชื่อแท็บที่มีอยู่จริงในสเปรดชีตนั้น
    """
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
        )
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
    station_id = authorized_station_id(station, session)
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
    station_id = authorized_station_id(station, session)
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
    """ผลงานรายสถานีคู่กับกำลังพลที่มีจริง และภารกิจเฉลี่ยต่อคน"""
    station_id = authorized_station_id(station, session)
    _require_division(session)
    try:
        data = hq_service.executive_overview(station_id, start or "", end or "")
    except SheetWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@app.get("/api/commander/calendar")
def commander_calendar(
    station: Optional[str] = None,
    month: Optional[str] = None,
    session: Dict[str, Any] = Depends(current_session),
):
    """ภารกิจที่ยังใช้งานอยู่ของเดือนนั้น สำหรับปฏิทินหน้าผู้กำกับการ"""
    station_id = authorized_station_id(station, session)
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
        raise HTTPException(status_code=502, detail="ส่งไม่สำเร็จ ยังไม่ได้ผูกกลุ่ม LINE ของสถานีปลายทาง")

    note = f" (ข้าม {len(skipped)} สถานีที่ยังไม่ได้ผูกกลุ่ม LINE)" if skipped else ""
    return {"status": "success", "message": f"ส่งข้อความสั่งการแล้ว {len(sent)} สถานี{note}"}


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
