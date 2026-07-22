"""
HWPD Next Gen - Configuration & Station Routing Engine
Ported from JS (รหัส.js) STATION_CONFIG & DB_ROUTER architecture.
"""

import os
import json
from typing import Dict, Any, List, Optional

# Master configuration loaded from environment or defaults
MASTER_SHEET_ID: str = os.getenv("MASTER_SHEET_ID", "186cb2LBLhfFD_6i-Z-kycPK_vGD4NZxkxCNI2MJop9A")
LINE_TOKEN: str = os.getenv("LINE_TOKEN", "")
SESSION_SECRET: str = os.getenv("SESSION_SECRET", "hwpd-sec-key-2026-secret")

# 🏛️ ฐานข้อมูลประจำกองกำกับการ 0-8 (Franchise Model)
# กอง 0 (บก.ทล. ส่วนกลาง), กอง 1-8 (กก.1 - กก.8)
DEFAULT_DB_ROUTER: Dict[str, Dict[str, str]] = {
    "0": {"OPS": ""},
    "1": {"OPS": "1Sgji6GHkgY1dlFei9jTiaW67-VFIu7zAf13PfwumQBc"},
    "2": {"OPS": ""},
    "3": {"OPS": ""},
    "4": {"OPS": ""},
    "5": {"OPS": "1R0x-rH8hfH9OXhtwVgxc9KKXv_d4xPYK1-0Sn13jkgA"},
    "6": {"OPS": ""},
    "7": {"OPS": ""},
    "8": {"OPS": ""},
}

# 🏢 โครงสร้างสถานีตำรวจทางหลวงประจำ กก.1-8
DEFAULT_STATION_CONFIG: Dict[str, Dict[str, Any]] = {
    "00": {"province": "ส่วนกลาง", "fullName": "กองบังคับการตำรวจทางหลวง", "units": ["บก.ทล."]},
    "10": {"province": "อยุธยา", "fullName": "ฝอ.กก.1 บก.ทล.", "units": ["ฝอ.กก.1"]},
    "11": {"province": "อยุธยา", "fullName": "ส.ทล.1 กก.1 บก.ทล.", "units": ["หน่วยฯอยุธยา", "หน่วยฯวังน้อย", "หน่วยฯประตูน้ำพระอินทร์"]},
    "12": {"province": "ลพบุรี", "fullName": "ส.ทล.2 กก.1 บก.ทล.", "units": ["หน่วยฯลพบุรี", "หน่วยฯโคกสำโรง"]},
    "13": {"province": "สิงห์บุรี", "fullName": "ส.ทล.3 กก.1 บก.ทล.", "units": ["หน่วยฯสิงห์บุรี", "หน่วยฯอินทร์บุรี"]},
    "14": {"province": "ชัยนาท", "fullName": "ส.ทล.4 กก.1 บก.ทล.", "units": ["หน่วยฯชัยนาท", "หน่วยฯมโนรมย์"]},
    "15": {"province": "สระบุรี", "fullName": "ส.ทล.5 กก.1 บก.ทล.", "units": ["หน่วยฯสระบุรี", "หน่วยฯแก่งคอย"]},
    "16": {"province": "นนทบุรี", "fullName": "ส.ทล.6 กก.1 บก.ทล.", "units": ["หน่วยฯนนทบุรี", "หน่วยฯบางบัวทอง"]},
    "50": {"province": "เชียงใหม่", "fullName": "ฝอ.กก.5 บก.ทล.", "units": ["ฝอ.กก.5"]},
    "51": {"province": "เชียงใหม่", "fullName": "ส.ทล.1 กก.5 บก.ทล.", "units": ["หน่วยฯดอนจาน", "หน่วยฯจอมทอง", "หน่วยฯฝาง", "หน่วยฯฮอด", "หน่วยฯอมก๋อย"]},
    "52": {"province": "ลำปาง", "fullName": "ส.ทล.2 กก.5 บก.ทล.", "units": ["หน่วยฯสบปราบ", "หน่วยฯห้างฉัตร", "หน่วยฯงาว"]},
    "53": {"province": "พิษณุโลก", "fullName": "ส.ทล.3 กก.5 บก.ทล.", "units": ["หน่วยฯเมืองพิษณุโลก", "หน่วยฯวังทอง", "หน่วยฯวัดโบสถ์"]},
    "54": {"province": "เชียงราย", "fullName": "ส.ทล.4 กก.5 บก.ทล.", "units": ["หน่วยฯแม่จัน", "หน่วยฯพะเยา", "หน่วยฯเชียงคำ"]},
    "55": {"province": "แพร่", "fullName": "ส.ทล.5 กก.5 บก.ทล.", "units": ["หน่วยฯเด่นชัย", "หน่วยฯน่าน", "หน่วยฯเวียงสา"]},
    "56": {"province": "ตาก", "fullName": "ส.ทล.6 กก.5 บก.ทล.", "units": ["หน่วยฯแม่สอด", "หน่วยฯสามเงา", "หน่วยฯสุโขทัย"]},
}


def get_db_router() -> Dict[str, Dict[str, str]]:
    """โหลด DB_ROUTER จาก Environment Variable หรือใช้ Default"""
    env_val = os.getenv("DB_ROUTER_JSON")
    if env_val:
        try:
            return json.loads(env_val)
        except Exception:
            pass
    return DEFAULT_DB_ROUTER


def get_station_config() -> Dict[str, Dict[str, Any]]:
    """โหลด STATION_CONFIG จาก Environment Variable หรือใช้ Default"""
    env_val = os.getenv("STATION_SECRETS_JSON")
    cfg = dict(DEFAULT_STATION_CONFIG)
    if env_val:
        try:
            secrets = json.loads(env_val)
            for st_id, s_data in secrets.items():
                if st_id in cfg:
                    cfg[st_id].update(s_data)
                else:
                    cfg[st_id] = s_data
        except Exception:
            pass
    return cfg


def get_station_data(station_id: str) -> Dict[str, Any]:
    """ดึงข้อมูลสถานีตาม Station ID (เทียบเท่า getStationData ใน JS)"""
    st_id = str(station_id or "").strip()
    config = get_station_config()
    if st_id in config:
        return config[st_id]

    division_num = st_id[0] if st_id else "5"
    return {
        "province": f"กองกำกับการ {division_num}",
        "fullName": f"ส.ทล.{st_id} กก.{division_num} บก.ทล.",
        "units": [f"หน่วยฯส.ทล.{st_id}"],
        "folderId": "",
        "lineGroupId": "",
    }


def get_target_db_id(station_id: str) -> str:
    """
    คืนค่า Spreadsheet ID สำหรับสถานี โดยดูจากตัวเลขแรก (กก.)
    เทียบเท่า getTargetDbId ใน JS
    """
    st_id = str(station_id or "").strip()
    division_num = st_id[0] if st_id else "5"
    db_router = get_db_router()

    div_entry = db_router.get(division_num)
    if not div_entry or not div_entry.get("OPS") or "ใส่_ID" in div_entry.get("OPS", ""):
        raise ValueError(
            f"กองกำกับการ {division_num} (สถานี {st_id}) ยังไม่ได้ตั้งค่าฐานข้อมูลปฏิบัติการ (DB_ROUTER) "
            "กรุณาติดต่อผู้ดูแลระบบส่วนกลางเพื่อระบุ ID ฐานข้อมูล"
        )

    return div_entry["OPS"]


def get_division_stations(station_id: str, include_hq: bool = False) -> List[str]:
    """
    คืนรายชื่อ Station ID ทั้งหมดที่สังกัด กองกำกับการ เดียวกัน
    เทียบเท่า getDivisionStations ใน JS
    """
    st_id = str(station_id or "").strip()
    div_num = st_id[0] if st_id else "5"
    config = get_station_config()

    stations = []
    for k in config.keys():
        if k.startswith(div_num):
            if not include_hq and (k.endswith("0") or k == "00"):
                continue
            stations.append(k)

    return sorted(stations)


def check_station_match(req_station_id: str, row_station_id: str) -> bool:
    """
    ตรวจสอบสิทธิ์มองเห็นตามระดับชั้นสถานี (Top-down Visibility)
    เทียบเท่า checkStationMatch ใน JS
    """
    req_st = str(req_station_id or "").strip()
    row_st = str(row_station_id or "").strip()

    if req_st == row_st:
        return True
    if req_st in ["00", "0", "HQ"]:
        return True
    if req_st.endswith("0") and req_st[0] == row_st[0]:
        return True

    return False
