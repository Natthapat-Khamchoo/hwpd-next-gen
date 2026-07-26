"""
HWPD Next Gen - Python FastAPI Backend Entry Point
Exposes REST Endpoints matching the Google Apps Script RPC contracts.
"""

import os

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
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

# Local user directory — mirrors the tb_Users Google Sheet (password: 1234).
# (Sheet-based lookup lives in app/services/user_service.py; not used yet by request.)
LOCAL_USERS = {
    "test": {"fullName": "ปลื้ม", "station": "50", "unit": "กองกำกับ", "role": "Super_Commander", "password": "1234", "phone": "0853565356", "code": "50"},
    "test2": {"fullName": "พี่ไอซ์", "station": "10", "unit": "กองกำกับ", "role": "HQ_Admin", "password": "1234", "phone": "0947632187", "code": "503"},
    "test3": {"fullName": "พี่ท้อป", "station": "70", "unit": "บก.", "role": "Division_Commander", "password": "1234", "phone": "0812882823", "code": "50005"},
    "test4": {"fullName": "พี่โอม", "station": "40", "unit": "บก.", "role": "Division_Admin", "password": "1234", "phone": "0824195636", "code": "510"},
    "test5": {"fullName": "พี่เท็น", "station": "23", "unit": "บก.", "role": "Station_Admin", "password": "1234", "phone": "0824195636", "code": "510"},
    "test6": {"fullName": "พี่บุช", "station": "51", "unit": "บก.", "role": "Unit_Staff", "password": "1234", "phone": "0824195636", "code": "510"},
}

app = FastAPI(
    title="HWPD Next Gen API",
    description="Python Backend API for Highway Police Division (บก.ทล.)",
    version="1.0.0",
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
    if not username:
        raise HTTPException(status_code=400, detail="กรุณาระบุ Username")

    # ตรวจสอบกับข้อมูลผู้ใช้ local (ตรงกับ tb_Users ในชีต) — ยังไม่ดึงจาก Google Sheet
    user = LOCAL_USERS.get(username.lower())
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
