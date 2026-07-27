"""
HWPD Next Gen - Configuration & Station Routing Engine
Ported from JS (รหัส.js) STATION_CONFIG & DB_ROUTER architecture.
"""

import os
import json
from typing import Dict, Any, List, Optional

try:  # python-dotenv is optional so `python -m unittest` works with no installs
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Master configuration loaded from environment or defaults
MASTER_SHEET_ID: str = os.getenv("MASTER_SHEET_ID", "186cb2LBLhfFD_6i-Z-kycPK_vGD4NZxkxCNI2MJop9A")
LINE_TOKEN: str = os.getenv("LINE_TOKEN", "")

# Secrets that spent time committed to this repo (source defaults and .env.example).
# Anyone with read access to the history can forge session tokens signed with them,
# so they are refused outright rather than merely discouraged.
BURNED_SESSION_SECRETS = frozenset(
    {
        "hwpd-sec-key-2026-secret",
        "hwpd-sec-key-2026-custom-secret",
    }
)


def get_session_secret() -> str:
    """
    คืนค่า SESSION_SECRET จาก Environment Variable
    ไม่มีค่า default เพราะ secret ที่ commit ลง git ใครก็ปลอม Session Token ได้
    """
    secret = os.getenv("SESSION_SECRET", "").strip()

    if not secret:
        raise RuntimeError(
            "SESSION_SECRET ยังไม่ได้ตั้งค่า ระบบจึงไม่สามารถเซ็น Session Token ได้\n"
            "  - เครื่อง dev: คัดลอก .env.example เป็น .env แล้วใส่ค่าที่สุ่มขึ้นมาเอง\n"
            "  - Render/production: ตั้งค่า Environment Variable ชื่อ SESSION_SECRET\n"
            "  สร้างค่าใหม่ด้วย: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )

    if secret in BURNED_SESSION_SECRETS:
        raise RuntimeError(
            "SESSION_SECRET ที่ตั้งไว้เป็นค่าที่เคยถูก commit ขึ้น git จึงถือว่ารั่วแล้ว "
            "กรุณาสร้างค่าใหม่ด้วย: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )

    return secret

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

# 🏢 โครงสร้างสถานีตำรวจทางหลวงประจำ กก.1-8 (43 สถานี + ฝอ.กก.1-8 + ส่วนกลาง)
# province มาจาก STATION_CONFIG_BASE ใน รหัส.js ส่วน units มาจากบัญชีหน่วยบริการที่หน่วยส่งมา
# fullName คำนวณจาก Station_ID ใน get_station_data จึงไม่ต้องเขียนซ้ำทุกสถานี
DEFAULT_STATION_CONFIG: Dict[str, Dict[str, Any]] = {
    "00": {"province": "ส่วนกลาง (บก.ทล.)", "fullName": "กองบังคับการตำรวจทางหลวง", "units": ["ฝอ.บก.ทล."]},

    # กก.1
    "10": {"province": "ฝอ.กก.1", "units": ["ฝอ.กก.1"]},
    "11": {"province": "อยุธยา", "units": ["วังน้อย", "รังสิต", "เอเซีย", "บางปะอิน", "นพวงศ์", "ราชพฤกษ์"]},
    "12": {"province": "สระบุรี", "units": ["พหลโยธิน เขต 1", "พหลโยธิน เขต 2", "เฉลิมพระเกียรติ", "ทับกวาง", "มิตรภาพ", "บ้านนา", "บางอ้อ"]},
    "13": {"province": "ลพบุรี", "units": ["เมืองลพบุรี", "โคกสำโรง", "ชัยบาดาล", "พัฒนานิคม"]},
    "14": {"province": "นครสวรรค์", "units": ["เขาหน่อ", "ราชรถ (เก้าเลี้ยว)", "ท่าน้ำอ้อย", "ท่าตะโก", "หนองบัว", "อุทัยธานี"]},
    "15": {"province": "เพชรบูรณ์", "units": ["ศรีเทพ", "ราหุล", "หล่มสัก", "เขาทราย", "วชิรบารมี"]},
    "16": {"province": "สิงห์บุรี", "units": ["อ่างทอง", "อินทร์บุรี", "สรรคบุรี", "ชัยนาท"]},

    # กก.2
    "20": {"province": "ฝอ.กก.2", "units": ["ฝอ.กก.2"]},
    "21": {"province": "นครปฐม", "units": ["สมุทรสงคราม", "มหาชัย", "ศรีสำราญ", "สาย 4", "ท่าตำหนัก", "หนองดินแดง", "ทัพหลวง", "กำแพงแสน", "บางเลน", "ดอนยายหอม", "บางโทรัด"]},
    "22": {"province": "เพชรบุรี", "units": ["บ้านโป่ง", "โพธาราม", "วังมะนาว", "เขตตรวจที่ 4", "ชะอำ"]},
    "23": {"province": "ประจวบคีรีขันธ์", "units": ["หัวหิน", "ห้วยมงคล", "กุยบุรี", "เกาะหลัก", "ทับสะเเก", "บางสะพาน", "ไชยราช"]},
    "24": {"province": "ชุมพร", "units": ["ท่าแซะ", "หลังสวน", "ทับหลี", "ระนอง"]},
    "25": {"province": "สุราษฎร์ธานี", "units": ["ไชยา", "เวียงสระ", "กาญจนดิษฐ์", "ท่าโรงช้าง"]},
    "26": {"province": "สุพรรณบุรี", "units": ["ท่ามะกา", "ไทรโยค", "พระแท่น", "อู่ทอง", "สาลี", "ศรีประจันต์", "ด่านช้าง"]},

    # กก.3
    "30": {"province": "ฝอ.กก.3", "units": ["ฝอ.กก.3"]},
    "31": {"province": "ฉะเชิงเทรา", "units": ["บางพลี", "บางปู", "เขตตรวจที่ 3 (บางปะกง)", "แปลงยาว", "บางคล้า", "สุวินทวงศ์", "พระประแดง"]},
    "32": {"province": "ชลบุรี", "units": ["สัตหีบ", "เขาคันทรง", "หนองใหญ่", "เขตตรวจที่ 6 (พนัสนิคม)"]},
    "33": {"province": "ระยอง", "units": ["มาบข่า", "วังจันทร์"]},
    "34": {"province": "จันทบุรี", "units": ["นายายอาม", "โป่งน้ำร้อน", "ขลุง"]},
    "35": {"province": "ปราจีนบุรี", "units": ["กบินบุรี", "สระแก้ว", "ศรีมหาโพธิ", "นาดี", "วังทอง"]},

    # กก.4
    "40": {"province": "ฝอ.กก.4", "units": ["ฝอ.กก.4"]},
    "41": {"province": "ร้อยเอ็ด", "units": ["โพนทอง", "รอบเมือง", "สุวรรณภูมิ", "พยัคฆภูมิพิสัย", "บรบือ", "ยางตลาด", "สมเด็จ"]},
    "42": {"province": "ขอนแก่น", "units": ["พล", "บ้านไผ่", "น้ำพอง", "หนองเรือ", "ชุมแพ", "รอบเมือง"]},
    "43": {"province": "อุดรธานี", "units": ["รอบเมือง", "โนนสะอาด", "หนองหาน", "หนองคาย", "บึงกาฬ"]},
    "44": {"province": "เลย", "units": ["วังสะพุง", "หนองบัวลำภู", "ภูเรือ", "เชียงคาน"]},
    "45": {"province": "สกลนคร", "units": ["สร้างค้อ", "พังโคน", "นครพนม"]},

    # กก.5
    "50": {"province": "ฝอ.กก.5", "units": ["ฝอ.กก.5"]},
    "51": {"province": "ตาก", "units": ["คลองขลุง", "นครชุม", "สามเงา", "แม่สอด", "เขตตรวจ 3"]},
    "52": {"province": "ลำปาง", "units": ["เถิน", "เกาะคา", "ห้างฉัตร", "งาว", "ลำพูน", "ลี้"]},
    "53": {"province": "พิษณุโลก", "units": ["บ้านป่า", "สีหราชเดโชชัย", "ทรัพย์ไพรวัลย์", "สุโขทัย", "ศรีสัชนาลัย"]},
    "54": {"province": "เชียงใหม่", "units": ["สารภี", "ฮอด", "แม่สะเรียง", "ดอยสะเก็ด", "แม่แตง", "เขตครวจฝาง"]},
    "55": {"province": "พะเยา", "units": ["แม่กา", "แม่อิง", "เชียงราย", "แม่จัน", "เชียงของ", "เขตตรวจ เวียงป่าเป้า"]},
    "56": {"province": "แพร่", "units": ["อุตรดิตถ์", "เด่นชัย", "แม่คำมี", "น่าน"]},

    # กก.6
    "60": {"province": "ฝอ.กก.6", "units": ["ฝอ.กก.6"]},
    "61": {"province": "นครราชสีมา", "units": ["กลางดง", "คลองไผ่", "สูงเนิน", "จอหอ", "บ้านส้ม", "สีดา", "ด่านขุนทด", "ปักธงชัย", "วังน้ำเขียว", "โชคชัย", "ห้วยแถลง", "ประทาย", "หนองบุญมาก"]},
    "62": {"province": "บุรีรัมย์", "units": ["โนนดินแดง", "นางรอง", "ประโคนชัย", "พุทไธสง", "เขตตรวจด่านชั่ง (หนองกี่)", "เขตตรวจรอบเมือง"]},
    "63": {"province": "สุรินทร์", "units": ["สังขะ", "ปราสาท", "ท่าตูม", "ศีขรภูมิ", "เขตตรวจรอบเมือง"]},
    "64": {"province": "อุบลราชธานี", "units": ["หนองไผ่", "เดชอุดม", "พิบูลมังสาหาร", "เขมราฐ", "เขื่องใน", "กันทรลักษ์", "อุทุมพร"]},
    "65": {"province": "อำนาจเจริญ", "units": ["ยโสธร", "มุกดาหาร", "นิคมคำสร้อย", "เขตตรวจปทุมราชวงศา"]},
    "66": {"province": "ชัยภูมิ", "units": ["คอนสาร", "ช่องสามหมอ", "ชัยภูมิ", "หนองบัวโคก", "เทพสถิต"]},

    # กก.7
    "70": {"province": "ฝอ.กก.7", "units": ["ฝอ.กก.7"]},
    "71": {"province": "พังงา", "units": ["กระบี่", "อ่าวลึก", "ตะกั่วป่า", "ภูเก็ต", "เขตตรวจที่ 1 (พังงา)"]},
    "72": {"province": "ตรัง", "units": ["เขตตรวจที่ 1", "ปะเหลียน", "ห้วยยอด", "พัทลุง", "ป่าบอน"]},
    "73": {"province": "สงขลา", "units": ["สิงหนคร", "จะนะ", "ทุ่งลุง", "รัตภูมิ", "สตูล"]},
    "74": {"province": "นครศรีธรรมราช", "units": ["หัวไทร", "สิชล", "ชะอวด", "ทุ่งสง"]},
    "75": {"province": "ปัตตานี", "units": ["บ่อทอง", "กลาพอ", "หน่วยกู้ภัยฯ นราธิวาส", "เขตตรวจยะลา"]},

    # กก.8
    "80": {"province": "ฝอ.กก.8", "units": ["ฝอ.กก.8"]},
    "81": {"province": "ชลบุรี(มอเตอร์เวย์)", "units": ["ลาดกระบัง", "พานทอง", "เขาเขียว", "บางละมุง", "มาบประชัน"]},
    "82": {"province": "ปทุมธานี(วงแหวน)", "units": ["รีพัฒน์", "ธัญบุรี", "ทับช้าง", "บางนา", "บางแค", "บางหญ่", "คูบางหลวง"]},
    "83": {"province": "นครราชสีมา(M6)", "units": ["มอเตอร์เวย์ M6(ลำตะคอง)"]},
    "84": {"province": "กาญจนบุรี(M81)", "units": ["บางแม่นาง", "ท่าม่วง"]},
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


def get_division_folders() -> Dict[str, str]:
    """
    โฟลเดอร์ Drive สำหรับเก็บไฟล์แนบของแต่ละ กก. (เลข กก. -> folder ID)
    ตั้งผ่าน DIVISION_FOLDERS_JSON
    """
    env_val = os.getenv("DIVISION_FOLDERS_JSON")
    if env_val:
        try:
            return {str(k): str(v) for k, v in json.loads(env_val).items()}
        except Exception:
            pass
    return {}


def get_division_folder_id(station_id: str) -> str:
    """คืนโฟลเดอร์ไฟล์แนบของ กก. ที่สถานีนั้นสังกัด"""
    st_id = str(station_id or "").strip()
    division_num = st_id[0] if st_id else "5"
    return get_division_folders().get(division_num, "")


def get_station_data(station_id: str) -> Dict[str, Any]:
    """
    ดึงข้อมูลสถานีตาม Station ID (เทียบเท่า getStationData ใน JS)

    ค่าที่ตั้งไว้ใน STATION_SECRETS_JSON จะทับค่าเริ่มต้นเฉพาะคีย์ที่ระบุ ทำให้ตั้งแค่
    folderId ของบางสถานีได้โดยไม่ทำให้ชื่อสถานีหายไป และถ้าสถานีไหนไม่ได้ตั้งโฟลเดอร์ไว้
    จะใช้โฟลเดอร์กลางของ กก. นั้นแทน
    """
    st_id = str(station_id or "").strip()
    division_num = st_id[0] if st_id else "5"
    station_num = st_id[1:] if len(st_id) > 1 else ""

    # เลขสถานีคือหลักที่สอง ไม่ใช่ทั้ง Station_ID — "51" คือ ส.ทล.1 กก.5 ไม่ใช่ ส.ทล.51
    # และหลักที่สองเป็น 0 หมายถึงฝ่ายอำนวยการของ กก. นั้น ไม่ใช่สถานี
    if station_num == "0":
        default_name = f"ฝอ.กก.{division_num} บก.ทล."
        default_units = [f"ฝอ.กก.{division_num}"]
    else:
        default_name = f"ส.ทล.{station_num} กก.{division_num} บก.ทล."
        default_units = [f"หน่วยฯส.ทล.{station_num} กก.{division_num}"]

    data: Dict[str, Any] = {
        "province": f"กองกำกับการ {division_num}",
        "fullName": default_name,
        "units": default_units,
        "folderId": "",
        "lineGroupId": "",
    }
    data.update(get_station_config().get(st_id, {}))

    if not data.get("folderId"):
        data["folderId"] = get_division_folder_id(st_id)

    return data


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
