# แมปข้อมูล: หน้าเว็บ → API → ชีต

เอกสารนี้ตอบสามคำถาม สำหรับทุกจุดที่ frontend คุยกับ backend

1. หน้า/ฟอร์มไหนเรียก endpoint อะไร
2. endpoint นั้นตอบกลับอย่างไรเมื่อยิงจริง
3. ข้อมูลที่กรอกเข้าไปไปลงชีตใด คอลัมน์ไหน

## วิธีที่ได้ตัวเลขมา

รัน backend ตัวจริงทั้งก้อน (`app.main`) แล้วสลับเฉพาะชั้นที่คุยกับ Google ออกเป็นตัวจำลอง
ในหน่วยความจำ — `sheets_service`, `storage_service`, `line_service` ทุกอย่างที่เหลือคือของจริง
ทั้งการตรวจสิทธิ์ การตรวจข้อมูล การประกอบแถว และการเขียน audit log

```
python python_backend/scripts/dev_server_fake_sheets.py    # :8000
python python_backend/scripts/sweep_endpoints.py           # ยิงทุก endpoint
```

ตัวจำลองบันทึกทุกการเขียนพร้อมจับคู่ค่ากับชื่อคอลัมน์ และบันทึกทุกตารางที่ถูกอ่าน
ตารางข้างล่างจึงเป็นสิ่งที่เกิดขึ้นจริง ไม่ใช่สิ่งที่อ่านจากโค้ดแล้วเดาเอา

ผลรอบล่าสุด **72 กรณี ผ่าน 71** — ที่ไม่ผ่านหนึ่งรายการอธิบายไว้ท้ายเอกสาร
(รอบก่อน 62 กรณี เพิ่ม 10 กรณีของชิ้นงาน PR และลิงก์สาธารณะ)

## ฟอร์มบันทึกรายงาน — เขียนลงชีต

| ฟอร์ม | คอมโพเนนต์ | endpoint | ลงตาราง |
|---|---|---|---|
| รายงานประจำวัน (แท็บ 1) | `DailyReportForm` | `POST /api/reports/daily` | `tb_DailyReport` |
| รายงานตั้งด่าน | `CheckpointForm` | `POST /api/reports/checkpoint` | `tb_Checkpoints` |
| รายงานการจับกุม | `ArrestForm` | `POST /api/reports/arrest` | `tb_Arrests` |
| ผลการปฏิบัติ/ว.20 (แท็บ 2) | `DailyReportForm` | `POST /api/reports/daily-result` | `tb_DailyResult` |
| เวรประจำสถานี (แท็บ 3) | `DailyReportForm` | `POST /api/reports/station-duty` | `tb_StationDuty` |
| สรุปยอดส่ง กก. (แท็บ 4) | `DailyReportForm` | `POST /api/reports/daily-summary` | `tb_HQ_Summary` |
| ภารกิจอื่น ๆ (แท็บ 5) | `DailyReportForm` | `POST /api/reports/other-duty` | `tb_OtherDuties` |
| รายงานอุบัติเหตุ | `AccidentForm` | `POST /api/reports/accident` | `tb_Accidents` |
| แจ้งภารกิจ | `MissionForm` | `POST /api/reports/mission` | `tb_Missions` |
| หมวดรายงานรับเสด็จ | `RoyalGuardForm` | `POST /api/reports/royal-guard` | `tb_RoyalGuard` |
| น้ำมัน / น้ำมันเครื่อง | `FuelForm` | `POST /api/reports/fuel` | `tb_FuelOil` |
| เซ็นเอกสารออนไลน์ | `DocumentForm` | `POST /api/reports/document` | `tb_Documents` |
| ตรวจรถบรรทุกน้ำหนักเกิน | `OverweightForm` | `POST /api/reports/overweight` | `tb_OverweightTrucks` |
| ส่งข่าวประชาสัมพันธ์ | `PrForm` | `POST /api/pr/news` | `tb_PR_News` + `tb_PR_Media` + `tb_AuditLog` |

### สองฟอร์มที่ตั้งใจไม่เขียนชีต

| ฟอร์ม | endpoint | ทำอะไรแทน |
|---|---|---|
| สรุปภารกิจ | `POST /api/reports/mission-summary` | รวมภารกิจที่บันทึกไว้แล้วส่งเข้า LINE ไม่ใช่รายการใหม่ |
| ออกเอกสารจับกุมอัตโนมัติ | `POST /api/reports/auto-arrest` | สร้างไฟล์จากแม่แบบ Google Docs คืนลิงก์ดาวน์โหลด |

## ช่องกรอก → คอลัมน์ในชีต

ทุกตารางเริ่มด้วยคอลัมน์ระบบเก้าช่องเหมือนกันหมด จึงยกมาไว้ที่เดียว

```
Sys_RecordID | Sys_Timestamp | Sys_LastUpdate | Sys_ActionBy | Sys_Status
Sys_IsActive | Data_ActualDate | Data_StationID | Data_UnitID
```

`Sys_ActionBy`, `Data_StationID`, `Data_UnitID` มาจาก session ไม่ใช่จากช่องกรอก
แก้ค่าใน request ก็ข้ามสถานีไม่ได้ เพราะ `authorized_station()` ยึดจาก token

### tb_DailyReport — รายงานประจำวัน

| ช่องกรอก (formData) | คอลัมน์ |
|---|---|
| `reportDateTime` | วันเวลาที่รายงาน |
| `dutyOfficer` | ผู้ปฏิบัติหน้าที่ประจำหน่วย (ชื่อและยศ) |
| `dutyPhone` | เบอร์โทร |
| `carNumber` | รถวิทยุตรวจเขต |
| `driverName` / `driverPhone` | พลขับ (ชื่อและยศ) / เบอร์โทรพลขับ |
| `radioOpName` / `radioOpPhone` | พนักงานวิทยุ (ชื่อและยศ) / เบอร์โทรพงว. |
| `startTime` / `endTime` | ปฏิบัติหน้าที่ตั้งแต่เวลา / ถึงเวลา |
| `camTotal` / `camReady` / `camBroken` | กล้องได้รับทั้งหมด / พร้อมใช้งาน / ใช้งานไม่ได้ (ตัว) |
| ไฟล์แนบ | Attachment_Folder |
| `officers[]` | ผู้ร่วมออก ว.4 เพิ่มเติม (JSON) |

### tb_Checkpoints — ตั้งด่าน

| ช่องกรอก | คอลัมน์ |
|---|---|
| `reportDateTime` | วันที่เวลาที่รายงาน |
| `dutyOfficer` | ยศ ชื่อ สกุล ตำแหน่ง ผู้รายงาน |
| `totalPersonnel` | จำนวนผู้ปฏิบัติรวม |
| `carNumber` | รถวิทยุตรวจเขต |
| `location` / `locationOther` | สถานที่/จุดตรวจ |
| `lat` / `lng` | ละติจูด / ลองจิจูด |
| ไฟล์แนบ | Attachment_Folder |

ละติจูด/ลองจิจูดเป็นคอลัมน์ที่เพิ่มตาม requirement ข้อ 6 ปุ่ม "ปักหมุด" กับ "ดึงพิกัด"
เขียนลงสองช่องนี้ และเป็นแหล่งข้อมูลของหมุดบนหน้าแผนที่

### tb_Arrests — จับกุม

| ช่องกรอก | คอลัมน์ |
|---|---|
| `reportDateTime` | วันที่เวลาที่รายงาน |
| `category` | หัวข้อการจับกุม |
| `arrestBy` | จับโดย |
| `arrestType` | ประเภทการจับกุม |
| `actionDateTime` | วันที่เวลาที่ดำเนินการ |
| `teamArray[]` | ชุดจับกุม (ต่อกันด้วยลูกน้ำ) |
| `suspectCount` | จำนวนผู้ต้องหา |
| `suspectArray[]` | ข้อมูลผู้ต้องหาทั้งหมด |
| `chargeArray[]` | ข้อหาทั้งหมด |
| `location` | สถานที่จับกุม |
| `lat` / `lng` | ละติจูด / ลองจิจูด |
| `seizedItems[]` | ของกลาง |
| `circumstances` | พฤติการณ์ |
| `forwarding` | การดำเนินการส่งต่อ |
| `caseNumber` | เลขคดี |
| `caseMethod` | ตรวจค้น/แจ้งข้อกล่าวหา |
| `damageValue` | มูลค่าความเสียหาย (บาท) |
| `turnoverValue` | วงเงินหมุนเวียน (บาท) |
| ไฟล์แนบ | Attachment_Folder |

### tb_DailyResult — ผลการปฏิบัติ / ว.20

| ช่องกรอก | คอลัมน์ |
|---|---|
| `reportDateTime` | วันเวลา |
| `v43` / `service` / `v42` / `v20` | ยอด ว.43 / ยอด บริการ / ยอด ว.42 / ยอด ว.20 |
| `charges[]` | Charges_Detail |
| `camTotal2` / `camReady2` / `camBroken2` | กล้องทั้งหมด / พร้อมใช้ / เสีย |
| `v20Warrant` | จับกุมตามหมายจับ (ราย) |
| `v20Flagrante` | จับกุมซึ่งหน้า (ราย) |
| ไฟล์แนบ | Attachment_Folder |

สองช่องท้ายเป็นคอลัมน์ที่เพิ่มตาม requirement ข้อ 12 (แยกหมายจับกับซึ่งหน้า)

### tb_StationDuty — เวรประจำสถานี

| ช่องกรอก | คอลัมน์ |
|---|---|
| `reportDateTime` | วันเวลาที่รายงาน |
| `inspectorName` / `inspectorPhone` | ร้อยเวร / เบอร์โทรร้อยเวร |
| `dutyOfficerName` / `dutyOfficerPhone` | สิบเวร / เบอร์โทรสิบเวร |
| `radioOpName` / `radioOpPhone` | พนักงานวิทยุ / เบอร์โทรพงว. |
| `startTime` / `endTime` | ตั้งแต่เวลา / ถึงวันที่ |

### tb_HQ_Summary — สรุปยอดส่ง กก.

ตารางนี้ใช้คอลัมน์ชุดสั้น ไม่ใช่เก้าคอลัมน์มาตรฐาน

```
Sys_RecordID | Sys_Timestamp | Data_StationID | Data_ReportDate
Sum_V43 | Sum_Service | Sum_V42 | Sum_V20 | Sum_Charges | Sys_ActionBy
```

`v43` → `Sum_V43`, `service` → `Sum_Service`, `v42` → `Sum_V42`, `v20` → `Sum_V20`,
`chargesText` → `Sum_Charges`

### tb_OtherDuties — ภารกิจอื่น ๆ

| ช่องกรอก | คอลัมน์ |
|---|---|
| `reportDateTime` | วันที่เวลา |
| `carNumber` | รถวิทยุตรวจเขต |
| `officers[]` | รายชื่อเจ้าหน้าที่ที่รวมเป็นข้อความแล้ว |
| `dutyType` / `dutyOtherText` | การปฏิบัติ |
| `actionDetails` | ดำเนินการ |
| `location` | สถานที่ |
| ไฟล์แนบ | Attachment_Folder |

### tb_Accidents — อุบัติเหตุ

| ช่องกรอก | คอลัมน์ |
|---|---|
| `reportDateTime` | วันที่เวลาเกิดเหตุ |
| `location` | ทล., กม., ตำบล, อำเภอ, จังหวัด |
| (ผู้บาดเจ็บ) | ผู้เสียชีวิต / บาดเจ็บ / รพ. |
| (ข้อมูลรถ) | รถหลัก / คู่กรณี |
| (สาเหตุ) | % สาเหตุ |
| `solutions` | แนวทางแก้ไข |
| `govDamage` | ความเสียหายของราชการ |
| `carNumber` | รถวิทยุที่ ว.4 |
| `jointUnits` | หน่วยร่วมปฏิบัติ |
| `description` | รายละเอียดพฤติการณ์ |
| `lat` / `lng` | ละติจูด / ลองจิจูด |
| `propDamageValue` | มูลค่าทรัพย์สินเสียหายรวม (บาท) |
| ไฟล์แนบ | Attachment_Folder |

### tb_Missions — แจ้งภารกิจ

| ช่องกรอก | คอลัมน์ |
|---|---|
| `reportDateTime` | วันที่เวลาที่แจ้ง |
| `startTime` / `endTime` | วันที่เวลาเริ่มภารกิจ / สิ้นสุดภารกิจ |
| `selectedUnits[]` | หน่วยบริการที่เกี่ยวข้อง (คั่นด้วยลูกน้ำ) |
| `missionDetails` | รายละเอียดภารกิจ |
| `location` | สถานที่ |
| ไฟล์แนบ | Attachment_Folde |

ชื่อคอลัมน์สุดท้ายสะกดตกตัว `r` จริง ๆ ในชีตที่ใช้งานอยู่ ระบบจึงรู้จักทั้งสองแบบ
ผ่าน `query_service.ATTACHMENT_COLUMNS` การแก้ชื่อคอลัมน์จะทำให้แถวเก่าอ่านไม่เจอ

### tb_RoyalGuard — รับเสด็จ

| ช่องกรอก | คอลัมน์ |
|---|---|
| `reportType` | prep=ปล่อยแถว, complete=เสร็จสิ้น |
| `reportDateTime` | วันเวลาที่กรอกในฟอร์ม |
| `commanders` | Commanders |
| `missionName` | ชื่อภารกิจ |
| `carNumbers` | หมายเลขรถวิทยุ |
| `details` | รายละเอียด หรือ ไทม์ไลน์ |
| `targetCount` | จำนวนที่หมาย |
| ไฟล์แนบ | FileUrl |

### tb_FuelOil — น้ำมัน

| ช่องกรอก | คอลัมน์ |
|---|---|
| `recordType` | ประเภทรายการ |
| `actionDateTime` | วันเวลาที่ทำรายการ |
| `actionPerson` | ผู้ดำเนินการ |
| `plateNumber` | ทะเบียนรถ |
| `currentMileage` | เลขไมล์ปัจจุบัน |
| `liters` | จำนวนลิตร |
| `fuelType` / `carType` | ประเภทน้ำมัน/รถ |
| `totalPrice` | ราคาบาท |
| `receiptNumber` | เลขที่ใบเสร็จ |
| สลิป | Slip_Attachment_Folder |

`Slip_Attachment_Folder` เป็นคอลัมน์ที่เพิ่มตาม requirement ข้อ 7

### tb_Documents — เซ็นเอกสารออนไลน์

| ช่องกรอก | คอลัมน์ |
|---|---|
| `reportDateTime` | Report_DateTime |
| `subject` | Doc_Subject |
| `docType` | Doc_Type |
| `senderName` | Sender_Name |
| (สถานะ) | Status |
| ไฟล์แนบ | Doc_File_Url |

### tb_OverweightTrucks — รถบรรทุกน้ำหนักเกิน

ตารางใหม่ทั้งใบตาม requirement ข้อ 14

| ช่องกรอก | คอลัมน์ |
|---|---|
| `reportDateTime` | วันที่เวลาที่ตรวจ |
| `inspectorName` | ผู้ตรวจ (ยศ ชื่อ สกุล) |
| `plateNumber` / `plateProvince` | ทะเบียนรถ / จังหวัดทะเบียน |
| `vehicleType` / `axleCount` | ประเภทรถ / จำนวนเพลา |
| `driverName` | ชื่อผู้ขับขี่ |
| `company` | บริษัท/ผู้ประกอบการ |
| `cargoType` | ประเภทสินค้าที่บรรทุก |
| `actualWeight` / `legalWeight` | น้ำหนักที่ชั่งได้ / ที่กฎหมายกำหนด (กก.) |
| (คำนวณให้) | น้ำหนักส่วนเกิน (กก.), เกินร้อยละ |
| `location` | สถานที่ตรวจ |
| `lat` / `lng` | ละติจูด / ลองจิจูด |
| `weighMethod` | วิธีการชั่ง |
| `action` / `charge` | ผลการดำเนินการ / ข้อหา |
| `caseNumber` | เลขที่ใบสั่ง/คดี |
| `remark` | หมายเหตุ |
| ไฟล์แนบ | Attachment_Folder |

สองคอลัมน์ที่คำนวณให้ backend คิดเองจากน้ำหนักสองช่อง ไม่รับค่าจากหน้าเว็บ
เพื่อไม่ให้ตัวเลขส่วนเกินขัดกับน้ำหนักที่บันทึกไว้

### tb_PR_News + tb_PR_Media — ประชาสัมพันธ์

ข่าวหนึ่งใบเขียนสองตาราง บวก `tb_AuditLog` หนึ่งแถว

`tb_PR_News` — `title` → หัวข้อข่าว, `source` → แหล่งที่มา, คำค้นที่ระบบจับได้ → คำค้นที่ตรวจพบ,
ไฟล์แนบ → Attachment_Folder

`tb_PR_Media` — หนึ่งแถวต่อหนึ่งไฟล์ ผูกกลับด้วย `News_RecordID`

```
ชื่อไฟล์ | ชนิดไฟล์ | ความกว้าง (px) | ความสูง (px) | ขนาดไฟล์ (ไบต์)
ผ่านเกณฑ์คุณภาพ | ที่มาของการตรวจ | File_Url
```

"ที่มาของการตรวจ" บอกว่าค่าความละเอียดมาจากเบราว์เซอร์หรือจาก Pillow ฝั่ง server
เพราะ backend วัดซ้ำเองแล้วใช้ค่าของตัวเองเมื่อวัดได้ (BR-01 วัดที่ด้านสั้น 1080)

อีกสี่คอลัมน์ใน `tb_PR_News` ไม่ได้มาจากฟอร์ม แต่เขียนตอนแอดมินกดสร้างลิงก์ (FR-07/08)

```
เทมเพลตชิ้นงาน PR | Share_File_ID | Share_Url | วันเวลาที่สร้างลิงก์
```

`Share_Url` แยกจาก `Permalink` โดยตั้งใจ — `Permalink` คือที่อยู่ของโพสต์บนเพจ (รอ FR-03)
ส่วน `Share_Url` คือไฟล์ข้อความที่ระบบสร้างเอง เก็บ `Share_File_ID` ไว้ด้วยเพราะการถอนสิทธิ์
สาธารณะต้องอ้างด้วย id ของไฟล์ ไม่ใช่ลิงก์

## หน้าธุรการ ฝอ.กก. / ผกก. — เขียนลงชีต

| หน้า | endpoint | ลงตาราง |
|---|---|---|
| `PrPanel` เพิ่มคำค้น | `POST /api/pr/keywords` | `tb_PR_Keywords` |
| `PrPanel` อนุมัติ/ปฏิเสธข่าว | `POST /api/pr/news/decide` | `tb_PR_News` + `tb_AuditLog` |
| `PrPanel` สร้างลิงก์สาธารณะ | `POST /api/pr/news/share` | `tb_PR_News` + `tb_AuditLog` |
| `PrPanel` ถอนลิงก์สาธารณะ | `POST /api/pr/news/share/revoke` | `tb_PR_News` + `tb_AuditLog` |
| `FuelPanel` ตั้งโควตา | `POST /api/hq/fuel/quota` | `tb_FuelQuota` |
| `ManpowerPanel` สถานะกำลังพล | `POST /api/hq/manpower/status` | `tb_Users` |
| `EvidencePanel` จัดหมวดของกลาง | `POST /api/hq/evidence` | `tb_Arrests` (แก้แถวเดิม) |
| `EscortPanel` บันทึกนำขบวน | `POST /api/hq/escort` | `tb_HQ_Escorts` |
| `ReferenceTableEditor` แก้แถว | `POST /api/admin/reference/{kind}` | `tb_Charges` ฯลฯ |
| `ReferenceTableEditor` เปิด/ปิด | `POST /api/admin/reference/{kind}/active` | `tb_Charges` ฯลฯ |
| `UserDirectory` แก้โปรไฟล์ | `POST /api/admin/users/update` | `tb_Users` |

## แก้ไข / อนุมัติ / ยกเลิก

| การกระทำ | หน้า | endpoint | ผลต่อชีต |
|---|---|---|---|
| ดูรายละเอียด | `RecordDetailModal` | `GET /api/records/detail` | อ่านอย่างเดียว |
| แก้ไขรายการตัวเอง | `RecordDetailModal` | `POST /api/records/update` | แก้เฉพาะช่องที่ส่งมา + `tb_AuditLog` |
| อนุมัติ | `StationAdminDashboard` | `POST /api/records/approve` | `Sys_Status` = Approved + `tb_AuditLog` |
| ยกเลิก | `MyHistoryForm` | `POST /api/records/cancel` | `Sys_Status` = Canceled, `Sys_IsActive` = FALSE + `tb_AuditLog` |

ทั้งสี่เส้นทางทดสอบผ่าน UI จริงแล้ว การแก้ไขจากเบราว์เซอร์ลงชีตถูกช่อง และมี audit log
คู่กันครบทุกครั้ง มี `Before_JSON` กับ `After_JSON` ให้ย้อนดูว่าใครแก้อะไร

ไม่มีเส้นทางไหนในระบบที่ลบแถวออกจากชีตจริง การยกเลิกคือ soft delete ทั้งหมด

## endpoint ที่อ่านอย่างเดียว — อ่านจากชีตไหน

| หน้า/คอมโพเนนต์ | endpoint | อ่านจาก |
|---|---|---|
| `useStationData` | `GET /api/dropdowns/units` | ค่าตั้งต้นในโค้ด ไม่แตะชีต |
| `useStationData` | `GET /api/dropdowns/users` | `tb_Users` |
| `useStationData` | `GET /api/dropdowns/user-phones` | `tb_Users` |
| `ChargeSelect` | `GET /api/dropdowns/charges` | `tb_Charges` |
| `ChargeSelect` / `AnalysisPanel` | `GET /api/dropdowns/charges-grouped` | `tb_Charges` |
| `MyHistoryForm` | `GET /api/my-pending` | 7 ตารางรายงาน |
| `StationAdminDashboard` | `GET /api/station-pending` | 7 ตารางรายงาน |
| `MissionViewForm` | `GET /api/missions` | `tb_Missions` |
| `DailyReportForm` แท็บ 4 | `GET /api/daily-summary` | `tb_Accidents`, `tb_Arrests`, `tb_DailyResult`, `tb_Missions`, `tb_OtherDuties`, `tb_RoyalGuard` |
| `HqDashboard` | `GET /api/division-summary` | ชุดเดียวกับ daily-summary |
| `HqAdminDashboard` | `GET /api/national-summary` | `tb_National_Summary` |
| `MapPanel` | `GET /api/map/points` | `tb_Accidents`, `tb_Arrests`, `tb_Checkpoints` |
| `SearchPanel` | `GET /api/search/division` `/national` | 7 ตารางรายงาน |
| `ReferenceTableEditor` | `GET /api/admin/reference/{kind}` | `tb_Charges` ฯลฯ |
| `UserDirectory` | `GET /api/admin/users` | `tb_Users` |
| `ReportExportPanel` | `GET /api/reports/catalog/exportable` | `tb_ReportCatalog` |
| `ReportExportPanel` | `GET /api/reports/export` | ตามรายงานที่เลือก คืนไฟล์ .xlsx |
| `SuperCommanderDashboard` | `GET /api/health/database` | เปิดสเปรดชีตตรง ไม่อ่านแท็บ |
| `FuelPanel` | `GET /api/hq/fuel` | `tb_FuelOil`, `tb_FuelQuota`, `tb_Users` |
| `ManpowerPanel` | `GET /api/hq/manpower` | `tb_Users` |
| `EvidencePanel` | `GET /api/hq/evidence` | `tb_Arrests` |
| `EscortPanel` | `GET /api/hq/escort` | `tb_HQ_Escorts`, `tb_Users` |
| `HqDashboard` | `GET /api/hq/daily-detail` | 5 ตารางรายงาน + `tb_Users` |
| `CommanderDashboard` | `GET /api/commander/overview` | 6 ตารางรายงาน + `tb_Users` |
| `CommanderDashboard` | `GET /api/commander/calendar` | `tb_Missions` |
| `CommanderDashboard` | `GET /api/commander/summary` | 5 ตารางรายงาน + `tb_HQ_Escorts` |
| `CommanderDashboard` | `GET /api/commander/divisions` | `DB_ROUTER` ไม่แตะชีต |
| `AnalysisPanel` | `GET /api/hq/analysis/categories` | หมวดในโค้ด ไม่แตะชีต |
| `PrPanel` | `GET /api/pr/news` | `tb_PR_News` |
| `PrPanel` / `PrForm` | `GET /api/pr/keywords` | `tb_PR_Keywords` |
| `PrPanel` | `GET /api/pr/templates` | เทมเพลตในโค้ด ไม่แตะชีต |
| `PrPanel` | `GET /api/pr/report/pending` | `tb_PR_News` |
| `HqAdminDashboard` | `GET /api/admin/aggregate-status` | สถานะในหน่วยความจำ ไม่แตะชีต |

`POST /api/hq/analysis` และ `POST /api/hq/comparison` เป็น POST ที่อ่านอย่างเดียว
ใช้ POST เพราะเงื่อนไขที่ส่งไปเป็นก้อน JSON ที่ยาวเกินกว่าจะใส่ใน query string

## กรณีที่ยิงแล้วไม่ผ่าน

**`POST /api/commander/order` ตอบ 502 "ยังไม่ได้ผูกกลุ่ม LINE ของสถานีปลายทาง"**

ไม่ใช่บั๊ก — เครื่องพัฒนายังไม่ได้ตั้ง `lineGroupId` ของสถานี 51 ไว้ในค่าคอนฟิก
สิ่งที่ควรสังเกตคือ endpoint นี้แยกสถานีที่ส่งสำเร็จกับที่ข้ามไปแล้วรายงานตามจริง
แทนที่จะตอบ success รวม ๆ ทั้งที่ไม่มีใครได้รับข้อความ ต้องเติมรหัสกลุ่มก่อนใช้งานจริง

## สิ่งที่พบระหว่างไล่ตรวจรอบนี้

| อาการ | สาเหตุ | แก้แล้ว |
|---|---|---|
| แอดมินส่วนกลางกดอนุมัติ/แชร์ข่าวแล้วได้ "กองกำกับการ 0 ยังไม่ได้ตั้งค่าฐานข้อมูล" | สถานีของ `HQ_Admin` คือ `"00"` ซึ่งไม่ใช่ กก. ไหน แต่โค้ดยึดสถานีจาก session ไปหาสเปรดชีต | รับ `station` จากหน้าเว็บผ่าน `authorized_station_id` (ไม่ใช่ `_for_stats` ซึ่งจะเปิดให้ ผกก. เขียนข้ามกอง) |
| error ของ gspread กลายเป็น 500 เปล่า ๆ ทุก endpoint | `SpreadsheetNotFound` / `APIError` ไม่ได้สืบทอด `SheetWriteError` ทุก `except` จึงจับไม่ติด | ตัวจัดการระดับแอปแปลงเป็น 502 พร้อมข้อความไทย |
| ลิงก์สาธารณะลอยเมื่อเขียนชีตไม่สำเร็จ ถอนจากหน้าเว็บไม่ได้อีก | อัปไฟล์และถอนของเก่าไปก่อนเขียนชีต พอเขียนพลาดจึงไม่มีรหัสไฟล์เก็บไว้ที่ไหนเลย | สลับเป็น อัป → เขียนชีต → ถอนของเก่า และถอนไฟล์ใหม่ทิ้งเมื่อเขียนพลาด |
| ช่วงวันที่ตั้งต้นของทุกหน้า ฝอ.กก. จบที่ "เมื่อวาน" ระหว่างเที่ยงคืนถึงเจ็ดโมงเช้า รายงานของเวรดึกจึงหายจากหน้าจอทั้งที่ลงชีตแล้ว | `panelHelpers.today()` ใช้ `toISOString()` ซึ่งคืนวันที่ตาม UTC ไทยเร็วกว่าเจ็ดชั่วโมง | ชดเชย timezone offset ก่อนตัดสตริง มีเทสคุมที่ `panelHelpers.test.ts` |
| `GET /api/health/database` ตอบ 500 เมื่อเปิดสเปรดชีตไม่ได้ | gspread โยน `SpreadsheetNotFound` ที่ไม่ได้สืบทอด error ของโปรเจกต์ จึงหลุด `except` | รับ exception ทุกชนิดต่อกอง รายงานเป็น status `error` |
| endpoint เดียวกันไม่มีการจำกัดสิทธิ์ | มีแค่ `current_session` ผู้ปฏิบัติทุกคนจึงอ่านรหัสสเปรดชีตทุกกองและอีเมลบัญชีบริการได้ | เพิ่ม `_require_hq()` ตามหน้าที่เรียกใช้จริง |
| ตารางประวัติการส่งอ่านไม่ออก พื้นขาวตัวหนังสือขาว | `<style>` ที่ scope ไว้ที่ `#formMyHistory` ในไฟล์ Apps Script เดิมไม่ได้ถูกย้ายมา | ยกกฎเดิมมาเป็นคลาส `.table-history` |
| ช่องวันที่ภาษาไทยค้างค่าเดิมเมื่อฟอร์มเปลี่ยนค่าจากข้างนอก | เทียบกับ `fp.input.value` ซึ่ง React เขียนทับไปแล้วตอน commit ก่อน effect จะรัน setDate จึงไม่เคยถูกเรียก | จำค่าที่ push เข้า flatpickr เอง |

## ข้อจำกัดของการทดสอบชุดนี้

ชั้น Google ถูกแทนด้วยตัวจำลอง สิ่งที่ยัง**ไม่ได้**พิสูจน์คือ

- โควตา 60 คำขอ/นาที ของ Google ภายใต้การใช้งานจริงพร้อมกันหลายหน่วย
- การอัปโหลดไฟล์เข้า Google Drive จริง (ตัวจำลองคืน URL ปลอม)
- การส่งข้อความเข้ากลุ่ม LINE จริง
- หัวคอลัมน์ในสเปรดชีตที่ใช้งานอยู่ตรงกับ `schema.py` หรือยัง — ต้องรัน
  `scripts/sync_sheet_headers.py` ตรวจกับชีตจริงก่อนขึ้นระบบ
