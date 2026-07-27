"""
รวบรวมค่าจาก .env บนเครื่องนี้ให้พร้อมวางลงหน้า Environment ของ Render

ผลลัพธ์เป็นไฟล์ที่มีค่าจริง จึงถูก gitignore ไว้ — ลบทิ้งเมื่อวางค่าครบแล้ว

    python scripts/export_render_env.py
    python scripts/export_render_env.py --out ที่อื่น.txt

`SESSION_SECRET` และ `CRON_SECRET` ไม่ถูกส่งออกโดยตั้งใจ ให้ Render สุ่มขึ้นมาเอง
ตาม render.yaml ค่าบนเครื่องพัฒนาไม่ควรไปโผล่บนเซิร์ฟเวอร์จริง
"""

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core import config  # noqa: E402,F401 — import แล้วโหลด .env ให้เอง

# (ชื่อตัวแปร, จำเป็นไหม, ผลถ้าไม่ตั้ง)
VARIABLES = [
    ("GOOGLE_OAUTH_CLIENT_ID", True, "เขียนชีตไม่ได้ ทุกอย่างตอบ 503"),
    ("GOOGLE_OAUTH_CLIENT_SECRET", True, "เขียนชีตไม่ได้ ทุกอย่างตอบ 503"),
    ("GOOGLE_OAUTH_REFRESH_TOKEN", True, "เขียนชีตไม่ได้ ทุกอย่างตอบ 503"),
    ("DB_ROUTER_JSON", True, "เหลือแค่ กก.1 กับ 5 ที่ส่งรายงานได้"),
    ("DIVISION_FOLDERS_JSON", True, "ไฟล์แนบถูกข้าม"),
    ("MASTER_SHEET_ID", False, "ใช้ค่าเริ่มต้นในโค้ด"),
    ("STATION_SECRETS_JSON", False, "ใช้ค่าเริ่มต้นใน STATION_CONFIG"),
    ("LINE_TOKEN", False, "ข้ามการแจ้งเตือน LINE"),
]

# ค่าที่ Render สุ่มเองตาม render.yaml — ห้ามยกค่าจากเครื่องพัฒนาไปใช้
GENERATED_ON_RENDER = ["SESSION_SECRET", "CRON_SECRET"]

PLACEHOLDER_PREFIXES = ("your_", "xxx", "<", "ใส่_", "ตัวอย่าง")


def looks_like_placeholder(value: str) -> bool:
    return value.lower().startswith(PLACEHOLDER_PREFIXES)


def main() -> int:
    parser = argparse.ArgumentParser(description="สร้างไฟล์ค่า Environment สำหรับ Render")
    parser.add_argument("--out", default="", help="ที่เก็บไฟล์ (ค่าเริ่มต้นตั้งชื่อตามวันที่)")
    args = parser.parse_args()

    lines = [
        "# ค่าสำหรับวางในหน้า Environment ของ Render service `hwpd-backend`",
        f"# สร้างเมื่อ {datetime.now():%Y-%m-%d %H:%M} จาก .env บนเครื่องพัฒนา",
        "# ไฟล์นี้มีความลับ — ลบทิ้งเมื่อวางค่าครบแล้ว",
        "",
    ]
    missing, placeholders = [], []

    for name, required, consequence in VARIABLES:
        value = os.getenv(name, "").strip()
        if not value:
            (missing if required else []).append(f"{name} — {consequence}")
            lines.append(f"# {name} ยังไม่ได้ตั้งบนเครื่องนี้ ({consequence})")
            continue
        if looks_like_placeholder(value):
            placeholders.append(f"{name} — {consequence}")
            lines.append(f"# {name} ยังเป็นค่าตัวอย่าง อย่าวางขึ้น Render ({consequence})")
            continue
        lines.append(f"{name}={value}")

    lines += [
        "",
        "# ตั้งเมื่อรู้โดเมนหน้าเว็บแล้ว ไม่ตั้ง = อนุญาตทุกโดเมน",
        "# CORS_ORIGINS=https://<โดเมนบน Vercel>",
        "",
        "# Render สุ่มค่าให้เองตาม render.yaml ห้ามยกค่าจากเครื่องพัฒนาไปใส่:",
        *[f"#   {name}" for name in GENERATED_ON_RENDER],
        "",
        "# PASSWORD_PEPPER ห้ามตั้ง — รหัสผ่านทุกบัญชี hash ด้วยค่าเริ่มต้นในโค้ด",
    ]

    out_path = args.out or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        f"render-env-{datetime.now():%Y%m%d_%H%M%S}.txt",
    )
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    print(f"เขียนไฟล์แล้ว: {out_path}")
    if missing:
        print("\nตัวแปรที่จำเป็นแต่ยังไม่มีค่าบนเครื่องนี้:")
        for item in missing:
            print(f"  - {item}")
    if placeholders:
        print("\nตัวแปรที่ยังเป็นค่าตัวอย่าง (ไม่ได้ใส่ลงไฟล์):")
        for item in placeholders:
            print(f"  - {item}")
    if not (missing or placeholders):
        print("ค่าที่จำเป็นครบทุกตัว")

    print("\nไฟล์นี้ถูก gitignore ไว้ ลบทิ้งเมื่อวางค่าบน Render ครบแล้ว")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
