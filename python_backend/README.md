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
│   │   ├── line_service.py   # สตรีมข้อความ Push Notification ไปยัง LINE Messaging API
│   │   ├── report_service.py # ประมวลผลและสร้าง Payload รายงาน (OP, CHK, ARR, ACC, MIS, RG, FUEL)
│   │   └── drive_service.py  # ระบบจัดการไฟล์อัปโหลด
│   └── main.py               # FastAPI App และ REST API Endpoints
├── tests/
│   ├── test_config.py        # Unit Tests การสืบค้น Routing ฐานข้อมูลตาม กก.
│   ├── test_security.py      # Unit Tests ความปลอดภัย Auth, HMAC, และ RBAC
│   └── test_sanitization.py # Unit Tests ป้องกัน Formula Injection
├── requirements.txt
├── .env.example
└── README.md
```

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

3. เข้าถึงเอกสาร API Interactive Swagger UI ได้ที่ `http://127.0.0.1:8000/docs`
