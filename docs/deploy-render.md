# นำระบบขึ้นใช้งานจริง

Backend อยู่บน Render (อ่าน `render.yaml`) หน้าเว็บอยู่บน Vercel
ค่าที่ต้องกรอกทั้งหมดอยู่ใน `.env` บนเครื่องพัฒนาแล้ว สร้างไฟล์สรุปไว้วางได้ด้วย

```bash
cd python_backend
python scripts/export_render_env.py
```

ไฟล์ที่ได้ถูก gitignore ไว้ ลบทิ้งเมื่อวางค่าครบแล้ว

---

## 1. Backend บน Render

**New + → Blueprint → เลือก repo นี้** Render จะอ่าน `render.yaml` แล้วถามค่าที่ตั้ง
`sync: false` ไว้ กรอกจากไฟล์ที่ export มา

| ตัวแปร | ไม่ตั้งแล้วเกิดอะไร |
|---|---|
| `SESSION_SECRET` | Render สุ่มให้เอง — ระบบไม่บูตถ้าไม่มี |
| `GOOGLE_OAUTH_CLIENT_ID` / `_SECRET` / `_REFRESH_TOKEN` | เขียนชีตไม่ได้ ทุกรายงานตอบ 503 และล็อกอินตอบ 503 |
| `DB_ROUTER_JSON` | เหลือแค่ กก.1 กับ กก.5 ที่มีค่าเริ่มต้น กก. อื่นตอบ 400 |
| `DIVISION_FOLDERS_JSON` | ไฟล์แนบถูกข้าม รายงานยังบันทึกได้แต่ตอบพร้อมคำเตือน |
| `MASTER_SHEET_ID` | ใช้ค่าเริ่มต้นในโค้ด ตั้งเมื่อจะย้ายชีต |
| `CORS_ORIGINS` | อนุญาตทุกโดเมน — ตั้งเป็นโดเมน Vercel เมื่อรู้แล้ว |
| `LINE_TOKEN` | ข้ามการแจ้งเตือน LINE รายงานยังบันทึกตามปกติ |
| `CRON_SECRET` | Render สุ่มให้เอง ใช้ในข้อ 3 |

**ห้ามตั้ง `PASSWORD_PEPPER`** รหัสผ่านทั้ง 52 บัญชีถูก hash ด้วยค่าเริ่มต้นในโค้ด
ตั้งค่าอื่นทับเมื่อไหร่ ทุกคนล็อกอินไม่ได้ทันที

### ตรวจหลัง deploy

```bash
curl https://<service>.onrender.com/
# {"system":"HWPD Next Gen Python API","status":"online","version":"1.0.0"}

# ล็อกอินเอา token
curl -X POST https://<service>.onrender.com/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"hq","password":"<รหัสจาก credentials CSV>"}'

# สถานะฐานข้อมูลรายกองกำกับ
curl https://<service>.onrender.com/api/health/database -H "x-token: <token>"
```

`/api/health/database` บอกรายกองว่าเชื่อมต่อได้ไหม เจอแท็บอะไรบ้าง และขาดตารางไหน

---

## 2. หน้าเว็บบน Vercel

Root directory `react_frontend` ตัวแปรที่ต้องตั้ง:

| ตัวแปร | ค่า |
|---|---|
| `VITE_API_BASE_URL` | `https://<service>.onrender.com/api` (ต้องมี `/api` ต่อท้าย) |

**อย่าตั้ง `VITE_DEMO_MODE`** ถ้าตั้งเป็น `true` หน้าเว็บจะแจ้งว่าบันทึกสำเร็จทั้งที่
ข้อมูลไม่ได้ถูกส่งไปไหน และเปิดให้ใครก็เข้าได้

เมื่อรู้โดเมน Vercel แล้ว กลับไปตั้ง `CORS_ORIGINS` บน Render ให้ตรง

---

## 3. ตั้งเวลารวมยอดระดับประเทศ

หน้า dashboard ของ ผบก. อ่านจาก `tb_National_Summary` ถ้าไม่มีอะไรมารวมยอด หน้านั้น
จะแสดงข้อมูลเก่าค้างไว้ ไม่ใช่ error

Render Cron Jobs ต้องเสียเงิน แผนฟรีจึงใช้ตัวตั้งเวลาภายนอกยิงเข้ามาแทน
(เช่น [cron-job.org](https://cron-job.org) ฟรี):

```
Method : POST
URL    : https://<service>.onrender.com/api/admin/aggregate-national?days=7
Header : x-cron-secret: <ค่า CRON_SECRET จาก Render>
ทุก    : 1 ชั่วโมง
```

ตอบกลับทันทีด้วย 202 แล้วทำงานต่อเบื้องหลัง งานเต็ม 8 กก. ใช้เวลาราวสองนาที
เพราะต้องรอโควตาการอ่านของ Google เป็นระยะ ยิงซ้อนกันได้ รอบที่สองจะถูกข้ามไป

รันเองจากเครื่องก็ได้:

```bash
cd python_backend
python scripts/aggregate_national.py --days 7 --verbose
python scripts/aggregate_national.py --dedupe     # ล้างแถวซ้ำที่ค้างจากระบบเดิม
```

---

## 4. เรื่องที่ยังค้าง

**แผนฟรีของ Render พักเครื่องเมื่อไม่มีคนใช้** คำขอแรกหลังพักจะรอราว 50 วินาที
เจ้าหน้าที่ที่กดล็อกอินครั้งแรกของวันจะเจออาการนี้ ถ้ารับไม่ได้ต้องขึ้นแผนเสียเงิน

**`LINE_TOKEN` ยังเป็นค่าตัวอย่างในเครื่องพัฒนา** (`your_line_messaging_...`) แปลว่า
การแจ้งเตือน LINE ยังไม่เคยทำงานจริงเลย ต้องเอา Channel Access Token จาก LINE
Developers Console มาใส่ และตั้ง `lineGroupId` รายสถานีใน `STATION_SECRETS_JSON`

**โฟลเดอร์ Drive ยังแชร์แบบ "ผู้ที่มีลิงก์แก้ไขได้"** ระบบไม่ได้พึ่งการแชร์แบบเปิดแล้ว
จึงปิดได้ แต่ต้องแชร์ตรงให้บัญชีที่ให้ consent ตอนสร้าง refresh token เป็น Editor
**ก่อน** แล้วจึงเปลี่ยนเป็นจำกัด ทำสลับลำดับจะหลุดสิทธิ์ตัวเอง

**`refresh_token` หมดอายุได้** ถ้าบัญชีเปลี่ยนรหัสผ่านหรือถอนสิทธิ์แอป ต้องรัน
`python scripts/get_oauth_token.py` ใหม่แล้วอัปเดตค่าบน Render อาการคือทุกอย่าง
ตอบ 503 พร้อมข้อความว่าเข้าถึง Google ไม่ได้
