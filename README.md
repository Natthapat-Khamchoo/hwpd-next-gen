# 🚔 HWPD Next Gen — ศูนย์ระบบรายงานและบริหารจัดการ บก.ทล.

ระบบรายงานการปฏิบัติงาน สถิติจับกุม และศูนย์ควบคุมสั่งการสำหรับ **กองบังคับการตำรวจทางหลวง (บก.ทล.)** ครอบคลุมการทำงานตั้งแต่ระดับเจ้าหน้าที่ปฏิบัติงานประจำหน่วยบริการ, สิบเวรประจำสถานี, ฝอ.กก.1-8, ผู้กำกับการ (ผกก.), ฝอ.บก.ทล., และผู้บังคับการ (ผบก.ทล.)

---

## 🏗️ โครงสร้างสถาปัตยกรรมโปรเจกต์ (Repository Layout)

```
hwpd-next-gen/
├── python_backend/        # 🐍 Modern Python FastAPI Engine & Business Logic Services
│   ├── app/
│   │   ├── core/          # Config, DB Router 0-8, Security (SHA-256, HMAC), Sanitization
│   │   ├── services/      # Report Processing, LINE Messaging API, Drive Upload
│   │   └── main.py        # FastAPI REST API Routes
│   ├── tests/             # Unit Test Suite (100% Pass)
│   └── requirements.txt   # Python Dependencies
├── react_frontend/         # ⚛️ Modern React Vite TypeScript Single Page Application (SPA)
│   ├── src/
│   │   ├── components/    # Glassmorphism UI Components (Forms, Dashboards, Navbar)
│   │   ├── context/       # Auth Context & Session Management
│   │   └── services/      # API Client integration with Python Backend
│   └── package.json
├── .gitignore
└── README.md
```

---

## ⚡ วิธีการเริ่มต้นใช้งานโปรเจกต์ (Getting Started)

### 1. 🐍 การเปิดใช้งาน Python Backend
```bash
cd python_backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
*เปิด Swagger API Documentation ได้ที่ `http://localhost:8000/docs`*

### 2. ⚛️ การเปิดใช้งาน React Frontend
```bash
cd react_frontend
npm install
npm run dev
```
*เข้าใช้งาน Web Interface ได้ที่ `http://localhost:5173`*

---

## 🔒 ความปลอดภัยและข้อควรระวัง (Security Policy)
- ห้าม Commit ไฟล์ `.env` หรือ API Tokens (`LINE_TOKEN`, Secret Keys) ขึ้นสู่ GitHub 
- ใช้ `.env.example` เป็นแม่แบบการตั้งค่าสภาพแวดล้อม
- ระบบรหัสผ่านถูกแฮชด้วย **SHA-256 + Pepper** และตรวจสอบเซสชันด้วย **HMAC Signed Tokens**
