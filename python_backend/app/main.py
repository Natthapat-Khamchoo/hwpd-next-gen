"""
HWPD Next Gen - Python FastAPI Backend Entry Point
Exposes REST Endpoints matching the Google Apps Script RPC contracts.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from typing import Dict, Any, List, Optional

from app.core.config import check_station_match, get_db_router, get_session_secret, get_target_db_id
from app.core.schema import TABLE_COLUMNS
from app.core.security import (
    verify_password,
    create_session_token,
    verify_session_token,
)
from app.services.report_service import (
    generate_record_id,
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
from app.services import sheets_service, user_service
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


app = FastAPI(
    title="HWPD Next Gen API",
    description="Python Backend API for Highway Police Division (บก.ทล.)",
    version="1.0.0",
    lifespan=lifespan,
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
        return append_report_row(prepared["targetDbId"], prepared["tableName"], prepared["rowData"])
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
        folder_url=attachments["folderUrl"],
        record_id=record_id,
    )
    return submit(prepared, attachments, "บันทึกรายงานการจับกุมเรียบร้อยแล้ว")


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
                    missingTables=[t for t in sorted(TABLE_COLUMNS) if t not in existing],
                )
            except (SheetNotConfigured, SheetWriteError) as exc:
                row.update(status="error", message=str(exc))
        elif sheet_id:
            row["status"] = "credentials_missing"

        report["divisions"].append(row)

    return report
