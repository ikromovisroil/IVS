"""
FCM (Firebase Cloud Messaging, HTTP v1) orqali mobil ilovaga (Android va iOS) push-xabarlar.

Sozlash (serverda):
  FIREBASE_CREDENTIALS_FILE=/path/to/firebase-service-account.json   (Firebase Console -> Project settings -> Service accounts)
  FIREBASE_PROJECT_ID=...   (ixtiyoriy; bo'lmasa JSON ichidan olinadi)
  pip install google-auth
  Docker'da: .env ga faqat FIREBASE_CREDENTIALS_PATH=<serverdagi JSON fayl> beriladi (docs/DOCKER.md).
  iOS uchun qo'shimcha: Firebase Console -> Cloud Messaging ga APNs kaliti yuklanishi shart.
Sozlanmagan bo'lsa FCM butunlay o'chiq turadi (hech narsa yuborilmaydi, xato ham bermaydi).

Bildirishnoma mazmuni mavjud push (web-push) bilan bir xil: title, body, url, tag. Qo'shimcha ravishda `data`
ichida ilova navigatsiyasi uchun `type` va tegishli ID (order_id, deed_id, conversation_id) beriladi.
"""
import logging
import os
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]
ANDROID_CHANNEL_ID = "ivs_default"   # ilovada shu ID bilan bildirishnoma kanali yaratilishi kerak

_creds_cache = {}

# tag (unikal hodisa belgisi) -> ilova uchun tur va ID maydonlari
_TAG_PATTERNS = [
    (re.compile(r"^order-new-(\d+)$"), "order_new", ("order_id",)),
    (re.compile(r"^order-status-(\d+)-(\w+)$"), "order_status", ("order_id", "status")),
    (re.compile(r"^order-assign-(\d+)$"), "order_assign", ("order_id",)),
    (re.compile(r"^deed-sender-(\d+)$"), "deed_sign", ("deed_id",)),
    (re.compile(r"^deed-watcher-(\d+)$"), "deed_agree", ("deed_id",)),
    (re.compile(r"^chat-ai-(\d+)$"), "chat", ("conversation_id",)),
    (re.compile(r"^chat-(\d+)$"), "chat", ("conversation_id",)),
]


class FcmTransientError(Exception):
    """Vaqtinchalik xato (tarmoq, 5xx, 429) — qayta urinib ko'riladi."""


def credentials_path() -> str:
    return getattr(settings, "FIREBASE_CREDENTIALS_FILE", "") or ""


def fcm_enabled() -> bool:
    path = credentials_path()
    # isfile va bo'sh emasligi: Docker'da fayl berilmasa o'rniga /dev/null ulanadi (yoki papka paydo bo'ladi)
    return bool(path) and os.path.isfile(path) and os.path.getsize(path) > 0


def _access_token():
    """(access_token, project_id) — service account JSON dan, muddati tugaganda yangilanadi."""
    from google.oauth2 import service_account
    import google.auth.transport.requests as google_requests

    path = credentials_path()
    creds = _creds_cache.get(path)
    if creds is None:
        creds = service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
        _creds_cache[path] = creds
    if not creds.valid:
        creds.refresh(google_requests.Request())
    project_id = getattr(settings, "FIREBASE_PROJECT_ID", "") or creds.project_id
    return creds.token, project_id


def build_data(title, body, url, tag) -> dict:
    """FCM `data` — barcha qiymatlar satr bo'lishi shart."""
    data = {"title": title or "", "body": body or "", "url": url or "/", "type": "general"}
    if tag:
        data["tag"] = tag
        for pattern, kind, keys in _TAG_PATTERNS:
            m = pattern.match(tag)
            if m:
                data["type"] = kind
                data.update({k: v for k, v in zip(keys, m.groups())})
                break
    return data


def _error_reason(response) -> str:
    try:
        err = response.json().get("error", {})
        details = " ".join(str(d.get("errorCode", "")) for d in err.get("details", []) if isinstance(d, dict))
        return f"{err.get('status', '')} {details}".strip()
    except Exception:
        return ""


def _android_block(tag) -> dict:
    return {
        "priority": "HIGH",
        "notification": {"channel_id": ANDROID_CHANNEL_ID, **({"tag": tag} if tag else {})},
    }


def _apns_block(tag, badge) -> dict:
    """iOS: ovoz, ilova belgisidagi o'qilmaganlar soni; bir xil tag eski bildirishnomani almashtiradi."""
    headers = {"apns-priority": "10", "apns-push-type": "alert"}
    if tag:
        headers["apns-collapse-id"] = tag[:64]   # APNs cheklovi: 64 bayt
    return {"headers": headers, "payload": {"aps": {"sound": "default", "badge": badge}}}


def send_to_employee(employee_id, title, body, url="/", tag=None) -> dict:
    """Xodimning barcha faol mobil qurilmalariga yuboradi. {"sent": n, "removed": n} qaytaradi."""
    from core.models import MobileDevice
    from core.notifications import unread_count

    result = {"sent": 0, "removed": 0}
    if not fcm_enabled():
        return result
    devices = list(MobileDevice.objects.filter(employee_id=employee_id, is_active=True))
    if not devices:
        return result

    token, project_id = _access_token()
    endpoint = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = build_data(title, body, url, tag)
    badge = unread_count(employee_id) if any(d.platform == "ios" for d in devices) else 0

    dead_ids = []
    transient = False
    for dev in devices:
        platform = {"apns": _apns_block(tag, badge)} if dev.platform == "ios" else {"android": _android_block(tag)}
        message = {
            "message": {
                "token": dev.token,
                "notification": {"title": title or "", "body": body or ""},
                "data": data,
                **platform,
            }
        }
        try:
            r = requests.post(endpoint, json=message, headers=headers, timeout=8)
        except requests.exceptions.RequestException:
            logger.exception("FCM ga ulanishda xato: employee_id=%s", employee_id)
            transient = True
            continue

        if r.status_code == 200:
            result["sent"] += 1
            continue

        reason = _error_reason(r)
        if r.status_code == 404 or "UNREGISTERED" in reason or "NOT_FOUND" in reason:
            dead_ids.append(dev.id)          # ilova o'chirilgan / token eskirgan
        elif r.status_code == 400 and "INVALID_ARGUMENT" in reason:
            dead_ids.append(dev.id)          # yaroqsiz token
        elif r.status_code in (401, 403):
            logger.error("FCM autentifikatsiya xatosi (sozlamani tekshiring): %s %s", r.status_code, r.text[:200])
        elif r.status_code == 429 or r.status_code >= 500:
            transient = True
        else:
            logger.error("FCM xatosi: %s %s", r.status_code, r.text[:200])

    if dead_ids:
        MobileDevice.objects.filter(id__in=dead_ids).delete()
        result["removed"] = len(dead_ids)
    if transient and result["sent"] == 0:
        raise FcmTransientError("FCM vaqtinchalik xato")
    return result
