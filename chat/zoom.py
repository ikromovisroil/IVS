"""
Zoom integratsiyasi (Server-to-Server OAuth). Zoom Marketplace'da "Server-to-Server OAuth" ilovasi yaratilib,
`meeting:write:admin` (yoki `meeting:write`) ruxsati beriladi; `Account ID`, `Client ID`, `Client Secret` .env ga yoziladi:

    ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET  (majburiy)
    ZOOM_HOST      — uchrashuvlar yaratiladigan Zoom foydalanuvchi (email yoki "me"; standart "me")
    ZOOM_TIMEZONE  — standart "Asia/Tashkent"

Sozlanmagan bo'lsa (`zoom_enabled()` False) uchrashuv yaratilmaydi, foydalanuvchiga tushunarli xabar chiqadi.
"""
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TOKEN_URL = "https://zoom.us/oauth/token"
API_URL = "https://api.zoom.us/v2"
TOKEN_CACHE_KEY = "zoom_s2s_token"
TIMEOUT = 15


class ZoomError(Exception):
    """Zoom bilan ishlashdagi xato (foydalanuvchiga ko'rsatilishi mumkin bo'lgan matn bilan)."""


def zoom_enabled() -> bool:
    return bool(
        getattr(settings, "ZOOM_ACCOUNT_ID", "")
        and getattr(settings, "ZOOM_CLIENT_ID", "")
        and getattr(settings, "ZOOM_CLIENT_SECRET", "")
    )


def _access_token() -> str:
    token = cache.get(TOKEN_CACHE_KEY)
    if token:
        return token
    try:
        resp = requests.post(
            TOKEN_URL,
            params={"grant_type": "account_credentials", "account_id": settings.ZOOM_ACCOUNT_ID},
            auth=(settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET),
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.exception("Zoom token so'rovi xatosi")
        raise ZoomError("Zoom bilan aloqa o'rnatilmadi. Birozdan keyin qayta urinib ko'ring.") from exc
    if resp.status_code != 200:
        logger.error("Zoom token xatosi: %s %s", resp.status_code, resp.text[:300])
        raise ZoomError("Zoom'ga kirib bo'lmadi (sozlamalarni tekshiring).")
    data = resp.json()
    token = data["access_token"]
    cache.set(TOKEN_CACHE_KEY, token, max(int(data.get("expires_in", 3600)) - 120, 60))
    return token


def _request(method: str, path: str, **kwargs):
    headers = {"Authorization": f"Bearer {_access_token()}"}
    try:
        resp = requests.request(method, f"{API_URL}{path}", headers=headers, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        logger.exception("Zoom API xatosi (%s %s)", method, path)
        raise ZoomError("Zoom bilan aloqa o'rnatilmadi. Birozdan keyin qayta urinib ko'ring.") from exc
    if resp.status_code == 401:
        cache.delete(TOKEN_CACHE_KEY)  # token eskirgan bo'lishi mumkin
    return resp


def create_meeting(topic: str, start_at_utc, duration_minutes: int, agenda: str = "") -> dict:
    """Uchrashuv yaratadi. Qaytaradi: {"id", "join_url", "start_url", "password"}."""
    host = getattr(settings, "ZOOM_HOST", "") or "me"
    waiting_room = bool(getattr(settings, "ZOOM_WAITING_ROOM", False))
    payload = {
        "topic": topic[:200],
        "type": 2,  # rejalashtirilgan uchrashuv
        "start_time": start_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration": int(duration_minutes),
        "timezone": getattr(settings, "ZOOM_TIMEZONE", "Asia/Tashkent"),
        "agenda": (agenda or "")[:2000],
        # Havola bilan kirgan hamma kutish xonasiga tushmasdan darhol qo'shiladi (ZOOM_WAITING_ROOM=1 bo'lsa — kutish xonasi yoqiladi).
        # Kirish kodi (passcode) Zoom tomonidan avtomatik beriladi va havolaga qo'shilgan.
        "settings": {
            "waiting_room": waiting_room,
            "join_before_host": not waiting_room,
            "host_video": True,
            "participant_video": False,
            "mute_upon_entry": True,
        },
    }
    resp = _request("POST", f"/users/{host}/meetings", json=payload)
    if resp.status_code == 401:
        resp = _request("POST", f"/users/{host}/meetings", json=payload)
    if resp.status_code not in (200, 201):
        logger.error("Zoom uchrashuv yaratilmadi: %s %s", resp.status_code, resp.text[:300])
        raise ZoomError("Zoom uchrashuvni yarata olmadi. Birozdan keyin qayta urinib ko'ring.")
    data = resp.json()
    return {
        "id": str(data["id"]),
        "join_url": data["join_url"],
        "start_url": data.get("start_url", ""),
        "password": data.get("password", ""),
    }


def get_invitation(zoom_id: str) -> str:
    """Zoom'ning tayyor taklif matni (havola, ID, kod, telefon raqamlari...). Olinmasa (masalan, ruxsat yo'q) — bo'sh matn."""
    try:
        resp = _request("GET", f"/meetings/{zoom_id}/invitation")
    except ZoomError:
        logger.warning("Zoom taklif matnini olib bo'lmadi (zoom_id=%s)", zoom_id)
        return ""
    if resp.status_code != 200:
        logger.warning("Zoom taklif matni berilmadi: %s %s", resp.status_code, resp.text[:200])
        return ""
    return (resp.json().get("invitation") or "").strip()


def end_meeting(zoom_id: str) -> bool:
    """Davom etayotgan uchrashuvni tugatadi. Uchrashuv hali boshlanmagan/allaqachon tugagan bo'lsa ham xato emas
    (vaqt bizning tizimda baribir bo'shatiladi). Zoom'da haqiqatan tugatilsa True."""
    try:
        resp = _request("PUT", f"/meetings/{zoom_id}/status", json={"action": "end"})
    except ZoomError:
        logger.warning("Zoom uchrashuvni tugatib bo'lmadi (zoom_id=%s)", zoom_id)
        return False
    if resp.status_code not in (200, 204):
        logger.info("Zoom uchrashuvni tugatmadi: %s %s", resp.status_code, resp.text[:200])
        return False
    return True


def delete_meeting(zoom_id: str) -> None:
    """Uchrashuvni Zoom'dan o'chiradi (allaqachon yo'q bo'lsa — xato emas)."""
    resp = _request("DELETE", f"/meetings/{zoom_id}", params={"schedule_for_reminder": "false"})
    if resp.status_code not in (200, 204, 404):
        logger.error("Zoom uchrashuv o'chirilmadi: %s %s", resp.status_code, resp.text[:300])
        raise ZoomError("Zoom uchrashuvni bekor qila olmadi.")
