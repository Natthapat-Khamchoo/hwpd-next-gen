# 🐍 HWPD Next Gen — Python Backend Engine

ระบบส่วนหลัง (Backend Engine) ของ **HWPD Next Gen (บก.ทล.)** ที่ได้รับการพอร์ตและถอดถอน Business Logic ออกจาก Google Apps Script (`รหัส.js`) มาเป็นภาษา Python 3.10+ ด้วยสถาปัตยกรรมแบบ Modular Architecture

---

## 📂 โครงสร้างโปรเจกต์ (Project Structure)

```
python_backend/
├── app/
│   ├── core/
│   │   ├── config.py         # โหลดคอนฟิก, STATION_CONFIG & DB_ROUTER Routing
│   │   ├── security.py       # ระบบ Password Hashing (SHA-256), HMAC Session Token, RBAC
│   │   └── sanitization.py   # ป้องกัน Formula Injection & HTML Escaping (XSS)
│   ├── services/
│   │   ├── line_service.py    # สตรีมข้อความ Push Notification ไปยัง LINE Messaging API
│   │   ├── report_service.py  # ประมวลผลและสร้าง Payload รายงาน (OP, CHK, ARR)
│   │   ├── storage_service.py # ตรวจสอบและถอดรหัสไฟล์แนบ (ตัวอัปโหลด Drive ยังไม่ได้ implement)
│   │   └── user_service.py    # อ่าน tb_Users จาก Master Sheet ผ่าน CSV export
│   └── main.py                # FastAPI App และ REST API Endpoints
├── tests/
│   ├── test_config.py         # Unit Tests การสืบค้น Routing ฐานข้อมูลตาม กก.
│   ├── test_security.py       # Unit Tests ความปลอดภัย Auth, HMAC, และ RBAC
│   ├── test_session_secret.py # Unit Tests ว่า SESSION_SECRET ต้องมาจาก environment
│   ├── test_storage.py        # Unit Tests การตรวจไฟล์แนบ
│   └── test_sanitization.py   # Unit Tests ป้องกัน Formula Injection
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🔑 ตั้งค่าก่อนรัน (บังคับ)

`SESSION_SECRET` ไม่มีค่า default ระบบจะไม่ยอมบูตถ้าไม่ได้ตั้งค่า เพราะ secret ที่ commit ลง git
ใครก็ปลอม Session Token เป็นสิทธิ์ระดับ ผบก. ได้

```bash
cd python_backend
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # เอาค่าที่ได้ไปใส่ SESSION_SECRET ใน .env
```

บน Render ให้ตั้ง Environment Variable ชื่อ `SESSION_SECRET` (blueprint `render.yaml` สั่ง generate
ให้อัตโนมัติสำหรับ service ที่สร้างใหม่ ส่วน service เดิมต้องเพิ่มเองก่อน deploy รอบถัดไป)

ค่าเดิม `hwpd-sec-key-2026-secret` และ `hwpd-sec-key-2026-custom-secret` ถูกขึ้นบัญชีดำไว้แล้ว
ระบบจะปฏิเสธไม่ให้ใช้

---

## 🗄️ เชื่อมฐานข้อมูล Google Sheets

รายงานทุกใบถูกเขียนลงสเปรดชีตของ กก. นั้น ๆ ผ่าน Service Account ถ้ายังไม่ได้ตั้งค่า
API จะตอบ `503` พร้อมข้อความบอกสาเหตุ ไม่ใช่รับรายงานแล้วปล่อยข้อมูลหาย

### 1. สร้าง OAuth Client ID

องค์กรบล็อกการสร้าง service account key (`iam.disableServiceAccountKeyCreation`)
จึงใช้ OAuth แทน ระบบจะทำงานเสมือนเป็นบัญชีที่กดอนุญาต **บัญชีนั้นต้องมีสิทธิ์แก้ไข
โฟลเดอร์ฐานข้อมูล** (เป็นเจ้าของ หรือถูกแชร์เป็น Editor ก็ได้)

1. เปิด [Google Cloud Console](https://console.cloud.google.com/) สร้างโปรเจกต์ (หรือใช้ของเดิม)
2. APIs & Services → Library → เปิดใช้งาน **Google Sheets API** และ **Google Drive API**
3. OAuth consent screen → **External** → กรอกชื่อแอปกับอีเมลติดต่อ
   → หัวข้อ **Test users** เพิ่มอีเมลบัญชีที่จะใช้กดอนุญาตเข้าไปด้วย
4. Credentials → Create credentials → **OAuth client ID** → Application type: **Desktop app**
5. ดาวน์โหลด JSON มาวางที่ `python_backend/client_secret.json` (`.gitignore` กันไว้แล้ว)

### 2. แลกเป็น refresh token

```bash
cd python_backend
pip install -r requirements.txt
python scripts/get_oauth_token.py
```

เบราว์เซอร์จะเปิดให้ล็อกอินด้วยบัญชีเจ้าของโฟลเดอร์แล้วกดอนุญาต เสร็จแล้วสคริปต์จะพิมพ์
`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN`
ให้เอาไปใส่ `.env` refresh token มีค่าเท่ากับรหัสผ่านของบัญชีสำหรับ Sheets/Drive ห้าม commit

### 3. สร้างตาราง

```bash
# ดูก่อนว่าจะสร้างอะไรบ้าง
python scripts/setup_database.py --divisions 5 --dry-run

# สร้างจริง
python scripts/setup_database.py --divisions 5
```

สคริปต์จะสร้างสองอย่างต่อหนึ่ง กก.

1. สเปรดชีต `DB_TEST_กก.{หมายเลข}` พร้อมแท็บ `tb_DailyReport`, `tb_Checkpoints`,
   `tb_Arrests` หัวคอลัมน์ชุดเดียวกับที่ Apps Script สร้างไว้ใน `DB_TEST_กก.1`
2. โฟลเดอร์ `กองกำกับ {หมายเลข}` สำหรับเก็บไฟล์แนบ (ข้ามได้ด้วย `--skip-folders`)

รันซ้ำได้ปลอดภัย ของที่มีอยู่แล้วจะถูกข้าม เมื่อเสร็จมันจะพิมพ์ค่า `DB_ROUTER_JSON`
และ `DIVISION_FOLDERS_JSON` ให้เอาไปใส่ `.env` หรือ Environment ของ Render

### ไฟล์แนบ

รายงานที่มีไฟล์แนบจะถูกอัปโหลดเข้าโฟลเดอร์ย่อยชื่อ `{รหัสรายงาน}_{ชื่อหน่วย}` ใต้โฟลเดอร์
ของ กก. นั้น แล้วเก็บลิงก์โฟลเดอร์ลงคอลัมน์ `Attachment_Folder` และข้อความ LINE
ตรงตามที่ Apps Script เคยทำ

ถ้า กก. ใดยังไม่ได้ตั้งค่าโฟลเดอร์ หรืออัปโหลดไม่สำเร็จ ระบบจะยังบันทึกรายงานลงชีต
แต่ตอบกลับพร้อมคำเตือนให้เจ้าหน้าที่เก็บไฟล์ต้นฉบับไว้ ไม่แจ้งว่าสำเร็จเฉย ๆ

ถ้าจะเติมแท็บที่ขาดลงสเปรดชีตที่มีอยู่แล้ว ใช้ `--spreadsheet-id`:

```bash
python scripts/setup_database.py --divisions 1 --spreadsheet-id 1Sgji6GHkgY1dlFei9jTiaW67-VFIu7zAf13PfwumQBc
```

### 4. ตรวจว่าต่อติดจริง

```bash
uvicorn app.main:app --reload --port 8000
```

ล็อกอินเอา token แล้วเรียก `GET /api/health/database` พร้อม header `x-token`
จะได้สถานะรายกองกำกับ ชื่อไฟล์ รายชื่อแท็บที่มีจริง และตารางที่ยังขาด

### 5. สร้างบัญชีประจำสถานี

```bash
# ดูว่าจะทำอะไรบ้าง ยังไม่เขียนอะไร
python scripts/create_station_users.py

# สร้างบัญชีที่ยังขาด
python scripts/create_station_users.py --apply

# อัปเดตชื่อหน่วย/สถานีของบัญชีเดิมให้ตรง STATION_CONFIG
python scripts/create_station_users.py --sync

# ลบบัญชีของสถานีที่ไม่มีใน STATION_CONFIG แล้ว
python scripts/create_station_users.py --prune
```

สร้าง 1 บัญชีต่อ 1 หน่วย รวม 52 บัญชี (43 สถานี + 8 ฝอ.กก. + ส่วนกลาง)

| Station_ID | Username | Role |
|---|---|---|
| `00` | `hq` | `Super_Commander` |
| `{กก.}0` | `fo{กก.}` | `Division_Admin` |
| `{กก.}{สถานี}` | `st{Station_ID}` | `Station_Admin` |

จำนวนสถานีไม่เท่ากันทุก กก. (กก.3, 4, 7 มี 5 สถานี กก.8 มี 4) สคริปต์อ่านรายชื่อจาก
`STATION_CONFIG` ไม่ได้สมมติจำนวนเอง เพิ่มสถานีใน config แล้วรัน `--apply` ได้เลย

บัญชีเหล่านี้ถูกกำกับ `AccountType=Unit` ในคอลัมน์ N ของ `tb_Users` เพราะใช้ชื่อสถานี
เป็น `FullName` ไม่ใช่ชื่อคน จึงถูกตัดออกจาก dropdown "ผู้รายงาน" และตารางเบอร์โทร
(ยังล็อกอินและส่งรายงานได้ตามปกติ) แถวที่ปล่อยคอลัมน์นี้ว่างไว้ถือเป็นบัญชีเจ้าหน้าที่
ชีตเก่าที่ยังไม่มีคอลัมน์นี้จึงทำงานได้เหมือนเดิม สคริปต์เติมหัวคอลัมน์ให้เองตอนรัน
`--apply` หรือ `--sync` ครั้งแรก และต่อท้ายเท่านั้น เพราะ Apps Script อ่านคอลัมน์ A-M
ด้วยตำแหน่ง

รหัสผ่านสุ่มความยาว 8 ตัวไม่ซ้ำกัน เก็บลงชีตเป็น `sha256$` ส่วนรหัสตัวจริงเขียนลง
`credentials_<วันเวลา>.csv` บนเครื่อง (gitignore ไว้แล้ว) เอาไว้แจกให้แต่ละหน่วย

### 6. สร้างบัญชีเจ้าหน้าที่ผู้ปฏิบัติ

```bash
# ดูว่าจะทำอะไรบ้าง ยังไม่เขียนอะไร
python scripts/create_operator_users.py

# สร้างบัญชีที่ยังขาด สถานีละ 1 คน
python scripts/create_operator_users.py --apply

# สถานีละหลายคน
python scripts/create_operator_users.py --per-station 2 --apply
```

| Station_ID | Username | Role | AccountType |
|---|---|---|---|
| `{กก.}{สถานี}` | `op{Station_ID}{ลำดับ}` | `Unit_Staff` | เว้นว่าง |

`Unit_Staff` เป็น role เดียวที่ไม่อยู่ใน `APPROVER_ROLES` (`app/main.py`) บัญชีกลุ่มนี้จึง
ส่งรายงานได้แต่อนุมัติไม่ได้ ต่างจากบัญชีในข้อ 5 ตรงที่เว้น `AccountType` ไว้ แปลว่าเป็น
บัญชีของคน ชื่อจึงไปโผล่ใน dropdown "ผู้รายงาน" ตามที่ตั้งใจ

ชื่อขึ้นต้น `op` ซึ่งไม่ตรง `OWNED_USERNAME` ของ `create_station_users.py` การรัน
`--prune` ของสคริปต์นั้นจึงไม่มาลบบัญชีกลุ่มนี้

**`FullName` เป็น placeholder** ขึ้นต้นด้วย `(รอระบุชื่อ)` เพราะตอนสร้างยังไม่มีรายชื่อจริง
ตารางนี้ออกแบบไว้ว่า 1 แถว = เจ้าหน้าที่ 1 นาย ระหว่างที่ยังไม่เติมชื่อ dropdown ผู้รายงาน
จะมีรายการ `(รอระบุชื่อ)` ปนอยู่ ค้นด้วยข้อความนั้นเพื่อตามเก็บ

### 7. รวมรหัสผ่านออกเป็น Excel สำหรับแจกหน่วย

```bash
python scripts/export_credentials_xlsx.py
```

หยิบ `credentials_*.csv` ล่าสุดของสองสคริปต์ข้างบนมารวมเป็นไฟล์เดียว ได้ชีตรวมหนึ่งชีต
แล้วแยกชีตราย กก. อีกชุด เพื่อส่งให้แต่ละกองโดยไม่ต้องกรองเอง และแต่ละกองไม่เห็นรหัส
ของกองอื่น

จังหวัดกับชื่อสถานีอ่านจาก `STATION_CONFIG` ปัจจุบัน ไม่ได้ลอกจาก CSV เพราะไฟล์ที่สร้าง
ไว้ก่อนข้อมูลสถานีถูกพอร์ตเข้ามา ยังมีจังหวัดเป็นค่า placeholder ค้างอยู่หกกองกำกับ

ไฟล์ผลลัพธ์มีรหัสผ่านแบบไม่เข้ารหัส ชื่อขึ้นต้น `credentials_` จึงถูก gitignore ไว้แล้ว
แจกครบเมื่อไหร่ลบทิ้ง และควรให้เจ้าหน้าที่เปลี่ยนรหัสหลังล็อกอินครั้งแรก
แล้วลบทิ้ง ทั้งสามโหมดรันซ้ำได้ และ `--prune` แตะเฉพาะบัญชีที่ตั้งชื่อตามรูปแบบข้างบน
จึงไม่ไปโดนบัญชีที่คนอื่นสร้างไว้

รหัสที่ hash แล้วผูกกับ `PASSWORD_PEPPER` ถ้าเปลี่ยนค่านี้ทีหลัง บัญชีทั้งหมดจะล็อกอินไม่ได้

### หมายเหตุเรื่อง schema

`app/core/schema.py` เก็บหัวคอลัมน์ของทุกตาราง และต้องเรียงตรงกับ `row_data` ที่
`prepare_*` ใน `report_service.py` สร้างขึ้น ถ้าไม่ตรง ข้อมูลจะลงผิดคอลัมน์โดยไม่มี error
`tests/test_schema.py` ตรวจข้อนี้ให้ทุกครั้งที่รันเทส เพิ่มรายงานประเภทใหม่เมื่อไหร่
ต้องเพิ่ม schema พร้อมกันเสมอ

---

## 🧪 การทดสอบชุดการทำงาน (Running Unit Tests)

รันชุดทดสอบความถูกต้องของโมดูล core logic ด้วยคำสั่งมาตรฐาน Python (ไม่จำเป็นต้องติดตั้ง External Packages):

```bash
cd python_backend
python -m unittest discover -s tests -p "test_*.py"
```

---

## 🚀 การเปิดใช้งานบริการ (Running FastAPI Server)

1. ติดตั้ง Dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. เริ่มต้น Server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

3. เอกสาร API (Swagger UI) ปิดไว้เป็นค่าเริ่มต้น เปิดตอนพัฒนาด้วย

   ```bash
   ENABLE_API_DOCS=true uvicorn app.main:app --reload --port 8000
   ```

   แล้วเข้าที่ `http://127.0.0.1:8000/docs` (มี `/redoc` กับ `/openapi.json` ด้วย)

   **อย่าตั้งตัวแปรนี้บนเซิร์ฟเวอร์จริง** สามหน้านี้ไม่ต้องล็อกอินและแจง endpoint
   ทั้งหมดพร้อมชื่อฟิลด์ทุกตัว ทุกเส้นยังต้องมี token อยู่ก็จริง แต่ไม่มีเหตุผลให้
   แจกแผนผังระบบกับคนนอก
