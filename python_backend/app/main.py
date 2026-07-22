"""
HWPD Next Gen - Python FastAPI Backend Entry Point
Exposes REST Endpoints matching the Google Apps Script RPC contracts.
"""

from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from app.core.config import (
    get_station_data,
    get_division_stations,
    check_station_match,
    DEFAULT_STATION_CONFIG,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_session_token,
    require_session,
)
from app.services.report_service import (
    prepare_daily_report,
    prepare_checkpoint_report,
    prepare_arrest_report,
)
from app.services.line_service import push_line_message

app = FastAPI(
    title="HWPD Next Gen API",
    description="Python Backend API for Highway Police Division (บก.ทล.)",
    version="1.0.0",
)


class LoginRequest(BaseModel):
    username: str
    password: str


class ReportSubmissionRequest(BaseModel):
    formData: Dict[str, Any]
    fileDataArray: Optional[List[Dict[str, Any]]] = None
    teamArray: Optional[List[str]] = None
    suspectArray: Optional[List[Dict[str, Any]]] = None
    chargeArray: Optional[List[str]] = None


@app.get("/")
def read_root():
    return {"system": "HWPD Next Gen Python API", "status": "online", "version": "1.0.0"}


@app.post("/api/login")
def login(req: LoginRequest):
    """
    ระบบล็อกอิน ตรวจสอบรหัสผ่าน SHA-256 / Plaintext และคืนค่า Session Token (HMAC)
    """
    username = req.username.strip()
    # ในการใช้งานจริง จะอ่านจาก tb_Users ใน Master Spreadsheet หรือ SQL DB
    if not username:
        raise HTTPException(status_code=400, detail="กรุณาระบุ Username")

    # ตัวอย่างข้อมูลผู้ใช้สำหรับการทดสอบ
    dummy_users = {
        "admin50": {"fullName": "ผู้ดูแล กก.5", "station": "50", "unit": "ฝอ.กก.5", "role": "Division_Admin", "password": "password123"},
        "super1": {"fullName": "ผู้บังคับการ", "station": "00", "unit": "บก.ทล.", "role": "Super_Commander", "password": "password123"},
    }

    user = dummy_users.get(username)
    if not user or not verify_password(username, req.password, user["password"]):
        return {"status": "error", "message": "Username หรือ Password ไม่ถูกต้อง"}

    token = create_session_token({"username": username, "role": user["role"], "station": user["station"]})
    return {
        "status": "success",
        "user": {
            "username": username,
            "fullName": user["fullName"],
            "station": user["station"],
            "unit": user["unit"],
            "role": user["role"],
            "token": token,
        },
    }


@app.post("/api/reports/daily")
def submit_daily_report(req: ReportSubmissionRequest, x_token: Optional[str] = Header(None)):
    """บันทึกรายงานประจำวัน (OP)"""
    res = prepare_daily_report(req.formData)
    # หากต้องการส่ง LINE push ทันที
    if res.get("lineGroupId"):
        push_line_message(res["lineMessage"], res["lineGroupId"])
    return {"status": "success", "message": "บันทึกข้อมูลและเตรียมส่งรายงานเรียบร้อยแล้ว", "recordId": res["recordId"]}


@app.post("/api/reports/checkpoint")
def submit_checkpoint_report(req: ReportSubmissionRequest, x_token: Optional[str] = Header(None)):
    """บันทึกรายงานตั้งด่าน (CHK)"""
    res = prepare_checkpoint_report(req.formData)
    if res.get("lineGroupId"):
        push_line_message(res["lineMessage"], res["lineGroupId"])
    return {"status": "success", "message": "บันทึกรายงานตั้งด่านเรียบร้อยแล้ว", "recordId": res["recordId"]}


@app.post("/api/reports/arrest")
def submit_arrest_report(req: ReportSubmissionRequest, x_token: Optional[str] = Header(None)):
    """บันทึกรายงานการจับกุม (ARR)"""
    res = prepare_arrest_report(
        req.formData,
        team_array=req.teamArray or [],
        suspect_array=req.suspectArray or [],
        charge_array=req.chargeArray or [],
    )
    if res.get("lineGroupId"):
        push_line_message(res["lineMessage"], res["lineGroupId"])
    return {"status": "success", "message": "บันทึกรายงานการจับกุมเรียบร้อยแล้ว", "recordId": res["recordId"]}
