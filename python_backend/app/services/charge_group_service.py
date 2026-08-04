"""
จัดกลุ่มฐานความผิดตาม พ.ร.บ. (requirement ข้อ 14)

หน่วยกำหนดกลุ่มหลักไว้ 4 พ.ร.บ. ของตำรวจทางหลวง ที่เหลือเข้ากลุ่ม "ข้อหาเฉพาะทาง"

**ที่มาของกลุ่มมีสองทาง เรียงตามลำดับความน่าเชื่อถือ**

1. คอลัมน์ F ในชีต `tb_Charges` ถ้ามีคนกรอกไว้ — ถือเป็นคำตอบสุดท้ายเสมอ
2. เดาจากคำในชื่อข้อหา เมื่อคอลัมน์นั้นว่าง

ข้อ 2 มีไว้เพื่อให้ระบบใช้งานได้ทันทีโดยไม่ต้องรอจัดกลุ่มข้อหาที่มีอยู่ทีละรายการ
**แต่การเดาจากคำไม่ใช่คำตอบทางกฎหมาย** ข้อหาที่เดาไม่ได้จะตกไปอยู่ "ข้อหาเฉพาะทาง"
ซึ่งเป็นที่ที่ปลอดภัยกว่าการเดาผิดกลุ่ม หน่วยควรไล่กรอกคอลัมน์ F ให้ครบก่อนใช้จริง
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# ชื่อกลุ่มและลำดับที่แสดงบนหน้าเว็บ ต้องเรียงตามนี้เสมอ
ACT_HIGHWAY = "พ.ร.บ.ทางหลวง"
ACT_LAND_TRANSPORT = "พ.ร.บ.ขนส่งทางบก"
ACT_VEHICLE = "พ.ร.บ.รถยนต์"
ACT_TRAFFIC = "พ.ร.บ.จราจรทางบก"
GROUP_SPECIAL = "ข้อหาเฉพาะทาง"

GROUP_ORDER: List[str] = [
    ACT_HIGHWAY,
    ACT_LAND_TRANSPORT,
    ACT_VEHICLE,
    ACT_TRAFFIC,
    GROUP_SPECIAL,
]

# คำที่ใช้เดากลุ่มเมื่อคอลัมน์ในชีตว่าง เรียงตามลำดับการตรวจ
# ตัวที่เจาะจงกว่าต้องมาก่อน ไม่งั้น "รถยนต์" จะไปคว้าข้อหาของ พ.ร.บ.ขนส่งไปด้วย
_KEYWORDS: List[tuple] = [
    (ACT_HIGHWAY, ("ทางหลวง", "เขตทางหลวง", "บรรทุกน้ำหนักเกิน", "น้ำหนักเกิน", "ทำให้เสียหายแก่ทาง")),
    (ACT_LAND_TRANSPORT, ("ขนส่ง", "รถโดยสาร", "ใบอนุญาตขับรถขนส่ง", "ประจำทาง", "ไม่ประจำทาง")),
    (ACT_VEHICLE, ("ทะเบียน", "ป้ายวงกลม", "ภาษีรถ", "สวมทะเบียน", "ป้ายปลอม", "ดัดแปลงสภาพรถ")),
    (
        ACT_TRAFFIC,
        (
            # "เร็วเกิน" ไม่ใช่ "ขับเร็ว" เพราะข้อหาจริงเขียนว่า "ขับรถเร็วเกินกว่า..."
            # ซึ่งมีคำว่า "รถ" คั่นอยู่ตรงกลาง การจับคำที่สั้นและอยู่ติดกันจริงจึงพลาดน้อยกว่า
            "จราจร", "เร็วเกิน", "ความเร็ว", "เมาแล้วขับ", "เมาสุรา", "แอลกอฮอล์",
            "หมวกนิรภัย", "เข็มขัดนิรภัย", "ฝ่าฝืนสัญญาณ", "สัญญาณไฟ", "แซง",
            "ย้อนศร", "ย้อนทาง", "โทรศัพท์", "จอดในที่ห้ามจอด",
        ),
    ),
]

# ข้อหาที่ requirement ข้อ 14 สั่งให้เพิ่มเข้าระบบ
#
# เก็บไว้ในโค้ดเพราะการเพิ่มแถวลงชีตต้องมี credentials ของ Google ซึ่งเครื่องที่พัฒนา
# ไม่มี ตัวนี้จึงถูกผสมเข้ารายการข้อหาเสมอแม้ยังไม่มีในชีต ถ้าวันหนึ่งแอดมินเพิ่มลงชีต
# เองแล้ว ระบบจะไม่แสดงซ้ำเพราะเทียบด้วยชื่อ
BUILTIN_CHARGES: Dict[str, str] = {
    "บุคคลต่างด้าว (ที่เกี่ยวกับ Scammer)": GROUP_SPECIAL,
}


def guess_group(charge_name: str) -> str:
    """เดากลุ่มจากคำในชื่อข้อหา คืน "ข้อหาเฉพาะทาง" เมื่อเดาไม่ได้"""
    text = str(charge_name or "")
    if not text.strip():
        return GROUP_SPECIAL
    if text in BUILTIN_CHARGES:
        return BUILTIN_CHARGES[text]
    for group, keywords in _KEYWORDS:
        if any(word in text for word in keywords):
            return group
    return GROUP_SPECIAL


def normalize_group(raw: str) -> str:
    """
    แปลงค่าที่คนกรอกในชีตให้ตรงกับชื่อกลุ่มมาตรฐาน คืนสตริงว่างถ้าไม่ตรงกลุ่มไหนเลย

    รับได้ทั้ง "พ.ร.บ.จราจรทางบก", "จราจรทางบก" และ "จราจร" เพราะคนกรอกจะพิมพ์
    ไม่เหมือนกัน การบังคับให้พิมพ์เป๊ะจะทำให้ข้อมูลที่กรอกมาแล้วใช้ไม่ได้
    """
    text = str(raw or "").strip()
    if not text:
        return ""
    for group in GROUP_ORDER:
        if text == group:
            return group
    compact = text.replace("พ.ร.บ.", "").replace(" ", "")
    for group in GROUP_ORDER:
        if compact and compact in group.replace("พ.ร.บ.", "").replace(" ", ""):
            return group
    return ""


def group_of(charge_name: str, sheet_value: str = "") -> str:
    """กลุ่มของข้อหาหนึ่งรายการ — ค่าที่กรอกในชีตชนะการเดาเสมอ"""
    return normalize_group(sheet_value) or guess_group(charge_name)


def grouped(charges: List[Dict[str, str]]) -> List[Dict[str, object]]:
    """
    จัดรายการข้อหาเป็นกลุ่มตามลำดับใน GROUP_ORDER

    รับ [{"name":..., "group":...}] คืน [{"group":..., "charges":[...]}]
    กลุ่มที่ไม่มีข้อหาเลยจะไม่ถูกส่งกลับ เพื่อไม่ให้หน้าเว็บมีหัวข้อว่าง ๆ
    """
    buckets: Dict[str, List[str]] = {group: [] for group in GROUP_ORDER}
    for item in charges:
        buckets.setdefault(item["group"], []).append(item["name"])

    return [
        {"group": group, "charges": buckets[group]}
        for group in GROUP_ORDER
        if buckets.get(group)
    ]
