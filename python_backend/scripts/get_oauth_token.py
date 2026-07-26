"""
ขอ OAuth refresh token สำหรับให้ backend เข้าถึง Google Sheets/Drive

ใช้เมื่อองค์กรบล็อกการสร้าง service account key (iam.disableServiceAccountKeyCreation)
ระบบจะทำงานในนามบัญชีที่กด "อนุญาต" ในขั้นตอนนี้ ไฟล์ที่สร้างจึงเป็นของบัญชีนั้น
และไม่ต้องแชร์โฟลเดอร์ให้ใครเพิ่ม

ขั้นตอนก่อนรัน:
  1. Google Cloud Console → APIs & Services → Library → เปิด Google Sheets API และ Google Drive API
  2. OAuth consent screen → เลือก External → กรอกชื่อแอปกับอีเมลติดต่อ
     → หัวข้อ Test users ให้เพิ่มอีเมลบัญชีที่เป็นเจ้าของโฟลเดอร์ไว้ด้วย
  3. Credentials → Create credentials → OAuth client ID → Application type: Desktop app
  4. ดาวน์โหลด JSON มาวางไว้ที่ python_backend/client_secret.json

จากนั้น:
    cd python_backend
    python scripts/get_oauth_token.py

เบราว์เซอร์จะเปิดให้ล็อกอินและกดอนุญาต เสร็จแล้วสคริปต์จะพิมพ์ค่า 3 ตัว
ให้เอาไปใส่ .env หรือ Environment ของ Render
"""

import argparse
import json
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.sheets_service import SCOPES  # noqa: E402

DEFAULT_CLIENT_SECRET = "client_secret.json"
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mask(value: str) -> str:
    """ย่อค่าลับให้พอยืนยันได้ว่าเขียนถูกตัว โดยไม่โชว์ของจริง"""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]} ({len(value)} ตัวอักษร)"


def upsert_env(path: str, values: dict) -> None:
    """เขียนค่าลง .env โดยแทนที่บรรทัดเดิมถ้ามีอยู่แล้ว และคงบรรทัดอื่นไว้ครบ"""
    lines = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    elif os.path.isfile(os.path.join(BACKEND_DIR, ".env.example")):
        with open(os.path.join(BACKEND_DIR, ".env.example"), "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        print("สร้าง .env ใหม่จาก .env.example")

    remaining = dict(values)
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        for key in list(remaining):
            if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
                lines[index] = f"{key}={remaining.pop(key)}"
                break

    for key, value in remaining.items():
        lines.append(f"{key}={value}")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="ขอ OAuth refresh token สำหรับ HWPD backend")
    parser.add_argument(
        "--client-secret",
        default=DEFAULT_CLIENT_SECRET,
        help=f"ไฟล์ OAuth client ID ที่ดาวน์โหลดจาก Cloud Console (ค่าเริ่มต้น: {DEFAULT_CLIENT_SECRET})",
    )
    parser.add_argument("--port", type=int, default=0, help="พอร์ตของ local server ที่ใช้รับ callback")
    parser.add_argument(
        "--write-env",
        action="store_true",
        help="เขียนค่าลง .env ให้เลย แทนที่จะพิมพ์ออกหน้าจอ (ปลอดภัยกว่าเวลาแชร์หน้าจอ)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.client_secret):
        print(f"ไม่พบไฟล์ {args.client_secret}", file=sys.stderr)
        print("ดาวน์โหลด OAuth client ID (Desktop app) จาก Cloud Console มาวางก่อน", file=sys.stderr)
        print("ขั้นตอนละเอียดอยู่ในคอมเมนต์หัวไฟล์นี้ และใน README", file=sys.stderr)
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ยังไม่ได้ติดตั้ง google-auth-oauthlib", file=sys.stderr)
        print("ติดตั้งด้วย: pip install -r requirements.txt", file=sys.stderr)
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, scopes=SCOPES)
    # access_type=offline + prompt=consent บังคับให้ Google ส่ง refresh token กลับมาเสมอ
    # ไม่งั้นบัญชีที่เคยอนุญาตแล้วจะได้แต่ access token ที่หมดอายุใน 1 ชั่วโมง
    creds = flow.run_local_server(port=args.port, access_type="offline", prompt="consent")

    if not creds.refresh_token:
        print("Google ไม่ได้ส่ง refresh token กลับมา", file=sys.stderr)
        print("ลองถอนสิทธิ์แอปที่ https://myaccount.google.com/permissions แล้วรันใหม่", file=sys.stderr)
        return 1

    with open(args.client_secret, "r", encoding="utf-8") as handle:
        client_config = json.load(handle)
    installed = client_config.get("installed") or client_config.get("web") or {}

    values = {
        "GOOGLE_OAUTH_CLIENT_ID": installed.get("client_id", ""),
        "GOOGLE_OAUTH_CLIENT_SECRET": installed.get("client_secret", ""),
        "GOOGLE_OAUTH_REFRESH_TOKEN": creds.refresh_token,
    }

    print()
    if args.write_env:
        env_path = os.path.join(BACKEND_DIR, ".env")

        # ระบบไม่ยอมบูตถ้า SESSION_SECRET ว่าง เติมให้ตั้งแต่ตอนนี้จะได้ไม่ไปสะดุดทีหลัง
        existing = ""
        if os.path.isfile(env_path):
            with open(env_path, "r", encoding="utf-8") as handle:
                existing = handle.read()
        if not any(
            line.strip().startswith("SESSION_SECRET=") and line.strip() != "SESSION_SECRET="
            for line in existing.splitlines()
        ):
            values["SESSION_SECRET"] = secrets.token_urlsafe(48)
            print("SESSION_SECRET ยังว่างอยู่ สุ่มค่าใหม่ให้ด้วย")

        upsert_env(env_path, values)
        print(f"เขียนค่าลง {env_path} เรียบร้อย:")
        for key, value in values.items():
            print(f"  {key} = {mask(value)}")
    else:
        print("สำเร็จ เอาสามบรรทัดนี้ไปใส่ .env (หรือ Environment ของ Render):")
        print()
        for key, value in values.items():
            print(f"{key}={value}")

    print()
    print("refresh token นี้มีค่าเท่ากับรหัสผ่านของบัญชีสำหรับ Sheets/Drive ห้าม commit ลง git")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
