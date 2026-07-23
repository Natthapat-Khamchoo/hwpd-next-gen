"""
HWPD Next Gen - User directory service.

Reads the `tb_Users` tab from the Master Spreadsheet (public "anyone with the
link" share) via the CSV export endpoint — no Google API credentials required.
Results are cached in-process for a short TTL so login stays fast.

Sheet columns: Username, Password, FullName, Station_ID, Unit_ID, Role,
สถานะไปช่วยราชการ, สถานะมาช่วยราชการ, หมายเหตุ, เบอร์โทร, รหัส, ...
"""

import csv
import io
import time
from typing import Dict, Any, Optional

import requests

from app.core.config import MASTER_SHEET_ID

_CACHE: Dict[str, Any] = {"users": None, "ts": 0.0}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _sheet_csv_url(sheet_name: str = "tb_Users") -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{MASTER_SHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    )


def _fetch_users() -> Dict[str, Dict[str, Any]]:
    """Fetch + parse tb_Users into a dict keyed by lowercase username."""
    resp = requests.get(_sheet_csv_url("tb_Users"), timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    reader = csv.DictReader(io.StringIO(resp.text))
    users: Dict[str, Dict[str, Any]] = {}
    for row in reader:
        username = (row.get("Username") or "").strip()
        if not username:
            continue
        users[username.lower()] = {
            "username": username,
            "password": (row.get("Password") or "").strip(),
            "fullName": (row.get("FullName") or "").strip(),
            "station": (row.get("Station_ID") or "").strip(),
            "unit": (row.get("Unit_ID") or "").strip(),
            "role": (row.get("Role") or "").strip(),
            "phone": (row.get("เบอร์โทร") or "").strip(),
            "code": (row.get("รหัส") or "").strip(),
        }
    return users


def get_all_users(force: bool = False) -> Dict[str, Dict[str, Any]]:
    """Return the cached user directory, refreshing when the TTL expires."""
    now = time.time()
    if not force and _CACHE["users"] is not None and (now - _CACHE["ts"]) < _CACHE_TTL_SECONDS:
        return _CACHE["users"]
    users = _fetch_users()
    _CACHE["users"] = users
    _CACHE["ts"] = now
    return users


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Look up one user by username (case-insensitive). None if not found or on fetch error."""
    key = (username or "").strip().lower()
    if not key:
        return None
    try:
        return get_all_users().get(key)
    except Exception:
        # On any fetch/parse failure, let the caller fall back to its own list.
        return None
