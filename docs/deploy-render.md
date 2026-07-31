# นำระบบขึ้นใช้งานจริง

Backend อยู่บน Render (อ่าน `render.yaml`) หน้าเว็บอยู่บน Vercel ตัวตั้งเวลารวมยอด
ใช้บริการภายนอก

เอกสารนี้เป็นขั้นตอนแบบกดตามทีละข้อ ค่าที่ต้องกรอกทั้งหมดอยู่ใน `.env` บนเครื่อง
พัฒนาแล้ว

**ลำดับสลับไม่ได้** Render กับ Vercel ต้องรู้โดเมนของกันและกัน

```
1. push โค้ดขึ้น GitHub
2. สร้าง service บน Render        → ได้ https://xxx.onrender.com
3. เอา URL นั้นไปตั้งบน Vercel     → deploy → ได้ https://yyy.vercel.app
4. กลับมาตั้ง CORS_ORIGINS บน Render ให้เป็นโดเมน Vercel
5. ตั้งตัวตั้งเวลารวมยอดระดับประเทศ
```

หน้าตา UI ของ Render กับ Vercel ขยับบ่อย ชื่อปุ่มอาจเพี้ยนไปบ้าง แต่ลำดับและค่าที่
ต้องกรอกเป็นไปตามนี้

---

## ส่วนที่ 0 — เตรียมค่าบนเครื่อง

**0.1** เปิด terminal ในโฟลเดอร์โปรเจกต์

```bash
cd python_backend
python scripts/export_render_env.py
```

**0.2** จะได้ข้อความประมาณนี้

```
เขียนไฟล์แล้ว: ...\python_backend\render-env-20260727_xxxxxx.txt

ตัวแปรที่ยังเป็นค่าตัวอย่าง (ไม่ได้ใส่ลงไฟล์):
  - LINE_TOKEN — ข้ามการแจ้งเตือน LINE
```

`LINE_TOKEN` ขึ้นเตือนถือว่าปกติ ข้ามไปก่อนได้ (ดูหัวข้อ 6.3)

**0.3** เปิดไฟล์ `render-env-xxxxx.txt` ค้างไว้ ในไฟล์มี 10 บรรทัดที่เป็น `ชื่อ=ค่า`
คือของที่ต้องกรอก ไฟล์นี้มีความลับและถูก gitignore ไว้ **ลบทิ้งเมื่อวางค่าครบแล้ว**

**0.4** เปิดไฟล์ `credentials_*.csv` ค้างไว้อีกไฟล์ หาแถวที่ `Username` = `hq`
จำรหัสผ่านไว้ ใช้ทดสอบในส่วนที่ 5

---

## ส่วนที่ 1 — Render (backend)

**1.1** เข้า [dashboard.render.com](https://dashboard.render.com) ล็อกอินด้วย GitHub

**1.2** มุมขวาบนกด **New +** แล้วเลือก **Blueprint**

**1.3** เลือก repo ถ้าไม่เห็น `hwpd-next-gen` ให้กด **Configure account** แล้วให้สิทธิ์
Render เข้าถึง repo นี้ก่อน

**1.4** เลือก `Natthapat-Khamchoo/hwpd-next-gen` แล้วกด **Connect**

**1.5** Render อ่าน `render.yaml` แล้วขึ้นชื่อ service `hwpd-backend` ช่อง
**Blueprint Name** ตั้งอะไรก็ได้

**1.6** ด้านล่างมีช่องให้กรอก กรอกจากไฟล์ในข้อ 0.3 เอาเฉพาะข้อความหลัง `=`

| ช่อง | กรอกอะไร |
|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | ลอกจากไฟล์ |
| `GOOGLE_OAUTH_CLIENT_SECRET` | ลอกจากไฟล์ |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | ลอกจากไฟล์ |
| `DB_ROUTER_JSON` | ลอกจากไฟล์ (JSON ยาวบรรทัดเดียว) |
| `DIVISION_FOLDERS_JSON` | ลอกจากไฟล์ (JSON ยาวบรรทัดเดียว) |
| `MASTER_SHEET_ID` | ลอกจากไฟล์ |
| `STATION_SECRETS_JSON` | ลอกจากไฟล์ |
| `AUTO_ARREST_DOC_ID` | ลอกจากไฟล์ |
| `AUTO_ARREST_M22_ID` | ลอกจากไฟล์ |
| `AUTO_ARREST_FOLDER_ID` | ลอกจากไฟล์ |
| `CORS_ORIGINS` | **เว้นว่าง** ยังไม่รู้โดเมน Vercel |
| `LINE_TOKEN` | **เว้นว่าง** ยังไม่มีค่าจริง |

ระวังตอน copy JSON อย่าให้ติดช่องว่างหรือ newline ท้ายมาด้วย

**1.7** `SESSION_SECRET` กับ `CRON_SECRET` จะไม่มีช่องให้กรอก เพราะ `render.yaml`
สั่งให้ Render สุ่มเอง ถูกต้องแล้ว **อย่าเพิ่มเอง** ค่าบนเครื่องพัฒนาไม่ควรไปโผล่บน
เซิร์ฟเวอร์จริง

**1.8** กด **Apply**

**1.9** รอ build ราว 3–5 นาที ดู log ได้ที่ tab **Logs** สำเร็จจะเห็นบรรทัดท้าย

```
Uvicorn running on http://0.0.0.0:10000
==> Your service is live
```

**1.10** ที่หัวหน้า service มี URL แบบ `https://hwpd-backend-xxxx.onrender.com`
copy เก็บไว้ เอกสารนี้เรียกว่า `<RENDER_URL>`

**1.11** ทดสอบทันที เปิด `<RENDER_URL>` ในเบราว์เซอร์ ควรได้

```json
{"system":"HWPD Next Gen Python API","status":"online","version":"1.0.0"}
```

**1.12** ไปที่ tab **Environment** หา `CRON_SECRET` กดไอคอนรูปตาเพื่อดูค่า
copy เก็บไว้ ใช้ในส่วนที่ 4

---

## ส่วนที่ 2 — Vercel (หน้าเว็บ)

**2.1** เข้า [vercel.com/dashboard](https://vercel.com/dashboard) เปิดโปรเจกต์

มีสามโปรเจกต์ที่ชี้มา repo นี้ — `hwpd-next-gen2` (ตัวจริง) `hwpd-next-gen-d398`
และ `hwpd-next-gen` ทั้งสามตั้งค่าเหมือนกัน และโดเมนทั้งสามต้องอยู่ใน
`CORS_ORIGINS` ข้อ 3.2

**2.2** ไปที่ **Settings → Build and Deployment** หา **Root Directory** ต้องเป็น
`react_frontend` ถ้าว่างหรือเป็นอย่างอื่น พิมพ์ `react_frontend` แล้ว **Save**

หน้าเดียวกัน **Framework Preset** ต้องเป็น **Vite** ถ้าเป็น Next.js จะหา `dist`
ไม่เจอแล้ว build ล้ม

ค่านี้ตั้งบน dashboard ที่เดียว ในรีโปไม่มี `vercel.json` แล้ว ตั้งใจเอาออก ของเดิม
สั่ง build จาก root ของรีโปซึ่งขัดกับ Root Directory เลือกได้ทางเดียว

พอตั้ง Root Directory แล้ว Vercel จะเปิด **Skip deployments** ให้เอง commit ที่ไม่ได้
แตะ `react_frontend/` จะไม่ build ใหม่ ปิดสวิตช์นั้นถ้าอยากให้ทุก commit ขึ้นเสมอ

ตั้งผิดข้อนี้ build จะพังตั้งแต่ขั้นแรก

**2.3** ไปที่ **Settings → Environment Variables** เพิ่ม

| ช่อง | ค่า |
|---|---|
| Key | `VITE_API_BASE_URL` |
| Value | `<RENDER_URL>/api` |

ตัวอย่างที่ถูก `https://hwpd-backend-xxxx.onrender.com/api`

**ต้องมี `/api` ต่อท้าย** และห้ามมี `/` ปิดท้าย เลือก Environment ทั้งสามอัน
(Production, Preview, Development) แล้ว **Save**

**2.4** **อย่าเพิ่ม `VITE_DEMO_MODE`** ถ้ามีอยู่แล้วให้ลบทิ้ง ค่านี้เป็น `true`
เมื่อไหร่ หน้าเว็บจะแจ้งว่าบันทึกสำเร็จทั้งที่ข้อมูลไม่ได้ถูกส่งไปไหน และเปิดให้ใคร
ก็เข้าได้

**2.5** ไปที่ tab **Deployments** เลือก deployment ล่าสุด กดจุดสามจุดขวามือแล้วเลือก
**Redeploy**

ค่า `VITE_*` ถูกฝังตอน build ไม่ใช่อ่านตอนรัน ตั้งค่าแล้วไม่ redeploy จะไม่มีผล

**2.6** รอ build เสร็จ ได้โดเมนแบบ `https://xxxx.vercel.app` copy เก็บไว้
เอกสารนี้เรียกว่า `<VERCEL_URL>`

**2.7** ตรวจว่า Vercel deploy จาก branch ไหน ดูที่ **Settings → Git →
Production Branch** งานทั้งหมดอยู่บน `main` แล้ว

---

## ส่วนที่ 3 — กลับมาปิด CORS ที่ Render

**3.1** กลับไป Render เปิด service `hwpd-backend` แล้วไปที่ tab **Environment**

**3.2** กด **Add Environment Variable**

| ช่อง | ค่า |
|---|---|
| Key | `CORS_ORIGINS` |
| Value | `<VERCEL_URL>` |

ตัวอย่าง `https://hwpd.vercel.app` — **ห้ามมี `/` ปิดท้าย** มีหลายโดเมนคั่นด้วย
จุลภาคไม่ต้องเว้นวรรค เช่น `https://a.vercel.app,https://b.vercel.app`

**3.3** กด **Save Changes** Render restart เองราวหนึ่งนาที

ไม่ตั้งค่านี้ระบบยังใช้ได้ แต่เปิดให้ทุกโดเมนเรียก API ได้

---

## ส่วนที่ 4 — ตัวตั้งเวลารวมยอดระดับประเทศ

หน้า dashboard ของ ผบก. อ่านจาก `tb_National_Summary` ถ้าไม่มีอะไรมารวมยอด หน้านั้น
จะแสดงข้อมูลเก่าค้างไว้ ไม่ใช่ error

Render Cron Jobs ต้องเสียเงิน แผนฟรีจึงใช้ตัวตั้งเวลาภายนอกยิงเข้ามาแทน
(เช่น [cron-job.org](https://cron-job.org) ฟรี)

**4.1** สมัครแล้วกด **Create cronjob**

**4.2** กรอก

| ช่อง | ค่า |
|---|---|
| Title | `HWPD national rollup` |
| URL | `<RENDER_URL>/api/admin/aggregate-national?days=7` |
| Schedule | ทุกชั่วโมง (นาทีที่ 0) |

**4.3** เปลี่ยน **Request method** จาก GET เป็น **POST**

**4.4** เปิดหัวข้อ **Advanced** ส่วน **Headers** เพิ่ม

| Name | Value |
|---|---|
| `x-cron-secret` | ค่า `CRON_SECRET` จากข้อ 1.12 |

**4.5** กด **Create** แล้วกด **Test run** ควรได้ HTTP **202** ทันที งานจริงทำต่อ
เบื้องหลังราวสองนาทีเพราะต้องรอโควตาการอ่านของ Google เป็นระยะ ยิงซ้อนกันได้
รอบที่สองจะถูกข้ามไป

ได้ 401 แปลว่า header ไม่ตรง

รันเองจากเครื่องก็ได้:

```bash
cd python_backend
python scripts/aggregate_national.py --days 7 --verbose
python scripts/aggregate_national.py --dedupe     # ล้างแถวซ้ำที่ค้างจากระบบเดิม
```

---

## ส่วนที่ 5 — ตรวจทั้งระบบ

**5.1** เปิด `<VERCEL_URL>` ควรเห็นหน้าล็อกอิน

**5.2** ล็อกอินด้วย `hq` กับรหัสจากข้อ 0.4

ค้างนาน 50 วินาทีแล้วค่อยเข้าได้ถือว่าปกติ ดูหัวข้อ 6.1

**5.3** ส่งรายงานประจำวันหนึ่งใบ แล้วเปิด Google Sheet ของ กก. นั้นดูว่าแถวลงจริง

**5.4** ตรวจสถานะฐานข้อมูลรายกองกำกับ

```bash
# ล็อกอินเอา token
curl -X POST <RENDER_URL>/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"hq","password":"<รหัสจาก credentials CSV>"}'

# สถานะรายกอง — บอกว่าเชื่อมต่อได้ไหม เจอแท็บอะไร ขาดตารางไหน
curl <RENDER_URL>/api/health/database -H "x-token: <token>"
```

**5.5** ลบไฟล์ `render-env-*.txt` ทิ้ง

---

## 6. เรื่องที่ยังค้าง

### 6.1 แผนฟรีของ Render พักเครื่องเมื่อไม่มีคนใช้

คำขอแรกหลังพักจะรอราว 50 วินาที เจ้าหน้าที่ที่กดล็อกอินครั้งแรกของวันจะเจออาการนี้
ถ้ารับไม่ได้ต้องขึ้นแผนเสียเงิน

### 6.2 `refresh_token` หมดอายุได้

ถ้าบัญชี Google เปลี่ยนรหัสผ่านหรือถอนสิทธิ์แอป ต้องรัน
`python scripts/get_oauth_token.py` ใหม่แล้วอัปเดตค่าบน Render อาการคือทุกอย่างตอบ
503 พร้อมข้อความว่าเข้าถึง Google ไม่ได้

### 6.3 `LINE_TOKEN` ยังเป็นค่าตัวอย่าง

การแจ้งเตือน LINE ยังไม่เคยทำงานจริงเลยสักครั้ง ต้องเอา Channel Access Token จาก
[LINE Developers Console](https://developers.line.biz) (เลือก channel แล้วไปที่
Messaging API) มาใส่ และตั้ง `lineGroupId` รายสถานีใน `STATION_SECRETS_JSON`

ส่วนที่เหลือของระบบไม่ขึ้นกับเรื่องนี้ ส่ง LINE ไม่ผ่านจะบันทึกไว้ในบันทึกระบบเฉย ๆ
รายงานที่บันทึกแล้วไม่กลายเป็นข้อผิดพลาด

### 6.4 การแชร์โฟลเดอร์ Drive

ไฟล์และโฟลเดอร์ทั้ง 20 รายการยังตั้งเป็น **"ทุกคนที่มีลิงก์ แก้ไขได้"** และไฟล์
`MASTER_TEST_National` มีแท็บ `tb_Users` ที่เก็บชื่อจริงและเบอร์โทรเจ้าหน้าที่
(รหัสผ่านเข้ารหัสแล้ว)

**ขั้นที่ 1 ทำแล้ว** บัญชีที่ระบบใช้ (`marsocas.1998@gmail.com`) ได้สิทธิ์ Editor
แบบระบุตัวครบทั้ง 20 รายการ ก่อนหน้านี้เข้าถึง 8 รายการได้ผ่านลิงก์สาธารณะเท่านั้น
ตรวจซ้ำได้ทุกเมื่อ:

```bash
python scripts/grant_system_access.py --verify
```

**ขั้นที่ 2 ยังไม่ได้ทำ** ยังไม่ปิดการแชร์แบบเปิด เพราะยังมีเพื่อนร่วมงานเปิดดูผ่าน
ลิงก์อยู่ ปิดตอนนี้จะตัดสิทธิ์คนเหล่านั้นทันที ลำดับที่ต้องทำ:

1. รวบรวมอีเมลของทุกคนที่ต้องเข้าถึง แล้วแชร์ตรงให้เป็น Editor หรือ Viewer
2. ตรวจว่าทุกคนเข้าได้จริงจากบัญชีตัวเอง
3. รัน `python scripts/grant_system_access.py --verify` ให้ผ่าน 20/20 อีกครั้ง
4. เปลี่ยนการแชร์ของโฟลเดอร์แม่ **ตัวเทส ระดับ บก.** เป็น "จำกัด"

ทำสลับลำดับ (ปิดก่อนแชร์) จะเข้าชีต `tb_Users` ไม่ได้ และล็อกอินพังทั้งระบบ ไฟล์ 8
รายการเป็นของ `pitchaya2419@gmail.com` การเปลี่ยนการแชร์ควรแจ้งเจ้าของก่อน

### 6.5 แม่แบบบันทึกจับกุมมีตัวยึดไม่ครบ

Google Docs API เปิดแล้ว เมนูออกเอกสารจับกุมทำงานจริง ทดสอบแล้วสร้างครบ บันทึกจับกุม
1 ฉบับ กับ ม.22,23 ตามจำนวนผู้ต้องหา ไม่มีตัวยึดค้างในเอกสาร

แต่แม่แบบบันทึกจับกุมมีตัวยึดแค่ 6 ตัว ไม่มีช่องเจ้าหน้าที่ผู้รับผิดชอบ ผู้แจ้ง และ
สถานที่ควบคุมตัว (ฉบับ ม.22,23 มีครบ 15 ตัว) ระบบส่งค่าเหล่านั้นไปให้อยู่แล้ว
เพิ่มตัวยึดลงในแม่แบบเมื่อไหร่จะถูกเติมให้เองโดยไม่ต้องแก้โค้ด

---

## 7. ปัญหาที่เจอบ่อย

| อาการ | สาเหตุ | แก้ |
|---|---|---|
| ทุกอย่างตอบ 503 | OAuth สามตัวไม่ครบ หรือ `refresh_token` ถูกเพิกถอน | ตรวจ Environment บน Render หรือรัน `get_oauth_token.py` ใหม่ |
| กก. บางกองตอบ 400 | `DB_ROUTER_JSON` ขาดหรือ JSON เพี้ยน | copy ใหม่ ระวัง newline ติดมา |
| หน้าเว็บขึ้น CORS error | `CORS_ORIGINS` ไม่ตรงโดเมน หรือมี `/` ปิดท้าย | แก้ให้ตรงเป๊ะ |
| ทุกคำขอตอบ 404 | `VITE_API_BASE_URL` ลืม `/api` | เติมแล้ว Redeploy |
| **ทุกคนล็อกอินไม่ได้พร้อมกัน** | มีคนตั้ง `PASSWORD_PEPPER` | ลบตัวแปรนั้นทิ้งทันที |
| ไฟล์แนบไม่ขึ้น Drive | `DIVISION_FOLDERS_JSON` ไม่ได้ตั้ง | เพิ่มบน Render |
| Vercel build fail ทันที | Root Directory ไม่ใช่ `react_frontend` หรือ Framework Preset ไม่ใช่ Vite | แก้ในข้อ 2.2 |
| ตัวตั้งเวลาได้ 401 | `x-cron-secret` ไม่ตรง `CRON_SECRET` | copy ค่าใหม่จาก Render |
| API ไม่บูตเลย | ไม่มี `SESSION_SECRET` | ตรวจว่า Render สุ่มค่าให้แล้ว |

**ห้ามตั้ง `PASSWORD_PEPPER`** รหัสผ่านทั้ง 58 บัญชีถูก hash ด้วยค่าเริ่มต้นในโค้ด
ตั้งค่าอื่นทับเมื่อไหร่ ทุกคนล็อกอินไม่ได้ทันที
