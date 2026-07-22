"""
HWPD Next Gen - LINE Messaging API Service
Ported from JS pushLineMessage
"""

import logging
import requests
from typing import Dict, Any
from app.core.config import LINE_TOKEN

logger = logging.getLogger(__name__)


def push_line_message(message: str, line_group_id: str, token: str = LINE_TOKEN) -> Dict[str, Any]:
    """
    ส่งข้อความแจ้งเตือนผ่าน LINE Messaging API (Push Message)
    เทียบเท่า pushLineMessage ใน JS
    """
    if not token or not line_group_id:
        return {"status": "skipped", "message": "LINE Token หรือ Group ID ยังไม่ได้ตั้งค่า"}

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "to": line_group_id,
        "messages": [{"type": "text", "text": message}],
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            return {"status": "success", "message": "ส่งข้อความ LINE เรียบร้อยแล้ว"}
        else:
            logger.error(f"LINE API Error ({response.status_code}): {response.text}")
            return {"status": "error", "message": f"LINE Push Error: {response.status_code}"}
    except Exception as e:
        logger.error(f"Failed to push LINE message: {e}")
        return {"status": "error", "message": str(e)}
