# 8.3 LINE Bot & Messaging API Skill
ครอบคลุมการพัฒนา LINE Bot ด้วย Messaging API, การจัดการ Webhook, การตรวจสอบ X-Line-Signature เพื่อความปลอดภัย, และการตอบกลับข้อความ (Reply Message)

### Best Practices สำหรับ LINE Bot
* **Signature Validation (สำคัญมาก)**: ต้องตรวจสอบ `X-Line-Signature` ใน Header ทุกครั้ง เพื่อป้องกันการยิง Webhook ปลอมจากภายนอก
* **Reply Token**: มีอายุเพียง 1 นาทีและใช้ได้ครั้งเดียว ต้องรีบตอบกลับภายในเวลาที่กำหนด
* **Idempotency**: LINE อาจส่ง Webhook Event เดิมซ้ำในบางกรณี ควรมีกลไกตรวจสอบ (เช่น เก็บ Event ID) เพื่อไม่ให้ระบบทำงานซ้ำซ้อน
* **Flex Message**: ใช้สำหรับสร้าง UI ที่สวยงามและซับซ้อน แทนการใช้ Text Message ธรรมดา

### Code Pattern (Python / FastAPI)
รูปแบบการเขียน Webhook สำหรับรับข้อความและตอบกลับด้วย FastAPI และ `line-bot-sdk`

```python
from fastapi import FastAPI, Request, HTTPException, Header
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os

app = FastAPI(title="LINE Bot API")

# โหลด Config จาก Environment Variables
line_bot_api = LineBotApi(os.environ.get("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("LINE_CHANNEL_SECRET"))

@app.post("/webhook")
async def line_webhook(request: Request, x_line_signature: str = Header(None)):
    # 1. รับ Raw Body จาก LINE
    body = await request.body()
    body_str = body.decode("utf-8")
    
    # 2. ตรวจสอบความถูกต้องของ Signature
    try:
        handler.handle(body_str, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature. Check your channel secret.")
    
    return "OK"

# 3. จัดการ Event ประเภท "ข้อความ (Message)"
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_msg = event.message.text
    user_id = event.source.user_id
    
    # ตัวอย่างการตอบกลับ (Echo)
    reply_text = f"คุณส่งข้อความว่า: {user_msg}"
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )