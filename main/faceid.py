"""
FaceID integratsiyasi (hujjatni yuz tekshiruvi bilan tasdiqlash): FaceID API mijozi, webhook imzosini tekshirish va
tekshiruv tugagach hujjatni tasdiqlash. Maxfiy kalitlar faqat serverning .env faylida (FACEID_*).

Oqim: sessiya yaratish (create_session) → ilovadagi SDK yuzni FaceID'ga yuboradi → FaceID webhook yuboradi →
callback_code bilan natija olinadi (get_data) → PINFL xodimnikiga mosligi tekshiriladi → hujjat tasdiqlanadi.
"""
import hashlib
import hmac
import logging
import time
from datetime import datetime, timedelta, timezone as dt_timezone

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

TOKEN_CACHE_KEY = "faceid_access_token"
TIMEOUT = 15

# Foydalanuvchiga ko'rsatiladigan matnlar (failure_reason bo'yicha); noma'lum kod — umumiy matn
FAILURE_MESSAGES = {
    "FACE_NOT_DETECTED": "Yuz topilmadi. Yuzingizni kadrga to'liq joylashtiring.",
    "INSUFFICIENT_FACE_FRAMES": "Yuz yetarlicha ko'rinmadi. Yorug' joyda, telefonni qimirlatmasdan urinib ko'ring.",
    "MULTIPLE_FACES": "Kadrda bir nechta yuz bor. Faqat o'zingiz qoling.",
    "QUALITY_LOW": "Surat sifati past. Yorug'roq joyga o'ting.",
    "CHALLENGE_FAILED": "So'ralgan harakat bajarilmadi. Ko'rsatmaga amal qilib qayta urinib ko'ring.",
    "SPOOF_DETECTED": "Tirik odam ekani tasdiqlanmadi. Rasm yoki ekran emas, o'zingiz kadrga qarang.",
    "FACE_MISMATCH": "Yuz davlat bazasidagi rasmga mos kelmadi. Qayta urinib ko'ring.",
    "DEPTH_FLAT": "Chuqurlik tekshiruvi o'tmadi. Yorug' joyda, telefonni qo'l masofasida ushlang.",
    "DEPTH_INSUFFICIENT": "Chuqurlik tekshiruvi o'tmadi. Yorug' joyda, telefonni qo'l masofasida ushlang.",
    "DEPTH_RGB_MISMATCH": "Chuqurlik tekshiruvi o'tmadi. Yorug' joyda, telefonni qo'l masofasida ushlang.",
    "IDENTITY_NOT_FOUND": "Shaxs davlat bazasida topilmadi. PINFL va tug'ilgan sanangizni tekshiring.",
    "GOVT_PHOTO_NO_FACE": "Davlat bazasidagi rasmdan foydalanib bo'lmadi. E-IMZO bilan tasdiqlang.",
    "GOVT_SERVICE_UNAVAILABLE": "Davlat xizmati vaqtincha ishlamayapti. Birozdan keyin urinib ko'ring.",
    "DEEPFAKE_SUSPECTED": "Tekshiruvdan o'tmadi. E-IMZO bilan tasdiqlang.",
    "ATTESTATION_FAILED": "Qurilma tekshiruvdan o'tmadi. Asl ilovadan foydalaning.",
    "MAX_ATTEMPTS_EXCEEDED": "Urinishlar tugadi. Qaytadan boshlang.",
    "SESSION_EXPIRED": "Tekshiruv vaqti tugadi. Qaytadan boshlang.",
    "SESSION_CANCELLED": "Tekshiruv bekor qilindi. Qaytadan boshlang.",
    "PINFL_MISMATCH": "Tekshirilgan shaxs hisobingizga mos kelmadi.",
    "CODE_EXPIRED": "Natija muddati o'tib ketdi. Qaytadan boshlang.",
    "CODE_ALREADY_USED": "Natija allaqachon ishlatilgan. Qaytadan boshlang.",
}
GENERIC_FAILURE = "Tekshiruvdan o'tmadi. Qaytadan urinib ko'ring yoki E-IMZO bilan tasdiqlang."
# Shu sabablarda yangi sessiyada qayta urinish foydasiz (E-IMZO tavsiya qilinadi)
NO_RETRY = {"IDENTITY_NOT_FOUND", "GOVT_PHOTO_NO_FACE", "DEEPFAKE_SUSPECTED", "ATTESTATION_FAILED", "PINFL_MISMATCH"}


class FaceIDError(Exception):
    def __init__(self, message, code="FACEID_ERROR", http_status=502):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def failure_message(reason: str) -> str:
    return FAILURE_MESSAGES.get(reason or "", GENERIC_FAILURE)


def enabled() -> bool:
    return bool(settings.FACEID_ENABLED)


def webhook_url() -> str:
    explicit = (getattr(settings, "FACEID_WEBHOOK_URL", "") or "").strip()
    if explicit:
        return explicit
    return settings.SITE_BASE_URL.rstrip("/") + "/api/v1/faceid/webhook/"


# ── imzo ────────────────────────────────────────────────────────────────────

def verify_signature(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    """X-FaceID-Signature: sha256=HMAC_SHA256(secret, "<timestamp>." + xom tana). Taqqoslash vaqtga bog'liq emas."""
    if not secret or not signature:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def timestamp_is_fresh(timestamp: str) -> bool:
    max_age = int(getattr(settings, "FACEID_WEBHOOK_MAX_AGE", 300))
    return timestamp.isdigit() and abs(time.time() - int(timestamp)) <= max_age


# ── FaceID API ──────────────────────────────────────────────────────────────

def _url(path: str) -> str:
    return settings.FACEID_HOST.rstrip("/") + path


def _error_from(response) -> FaceIDError:
    code, message = "FACEID_ERROR", "FaceID xizmati xato qaytardi"
    try:
        err = (response.json() or {}).get("error") or {}
        code = err.get("code") or code
        message = err.get("message") or message
    except ValueError:
        pass
    logger.warning("FaceID xatosi: http=%s code=%s", response.status_code, code)
    return FaceIDError(message, code=code, http_status=response.status_code)


def _access_token(force=False) -> str:
    if not force:
        token = cache.get(TOKEN_CACHE_KEY)
        if token:
            return token
    try:
        response = requests.post(
            _url("/api/v1/auth/access-token"),
            json={"client_id": settings.FACEID_CLIENT_ID, "client_secret": settings.FACEID_CLIENT_SECRET},
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        logger.exception("FaceID bilan aloqa xatosi (token)")
        raise FaceIDError("FaceID xizmati bilan aloqa yo'q", code="FACEID_UNREACHABLE", http_status=502)
    if response.status_code != 200:
        raise _error_from(response)
    data = response.json()
    token = data.get("access_token")
    if not token:
        raise FaceIDError("FaceID token qaytarmadi")
    cache.set(TOKEN_CACHE_KEY, token, max(int(data.get("expires_in", 3600)) - 60, 60))
    return token


def _call(method: str, path: str, **kwargs):
    """Token bilan so'rov; INVALID_TOKEN (401) kelsa tokenni yangilab bir marta qaytaradi."""
    for attempt in (0, 1):
        headers = {"Authorization": f"Bearer {_access_token(force=bool(attempt))}", **kwargs.pop("headers", {})}
        try:
            response = requests.request(method, _url(path), headers=headers, timeout=TIMEOUT, **kwargs)
        except requests.RequestException:
            logger.exception("FaceID bilan aloqa xatosi (%s)", path)
            raise FaceIDError("FaceID xizmati bilan aloqa yo'q", code="FACEID_UNREACHABLE", http_status=502)
        if response.status_code == 401 and attempt == 0:
            cache.delete(TOKEN_CACHE_KEY)
            continue
        return response


def create_session(pinfl: str, birth_date, idempotency_key: str, metadata: dict) -> dict:
    response = _call(
        "POST", "/api/v2/sdk/sessions",
        headers={"Idempotency-Key": idempotency_key},
        json={
            "method": "pinfl",
            "pinfl": pinfl,
            "birth_date": birth_date.isoformat(),
            "webhook_url": webhook_url(),
            "metadata": metadata,
        },
    )
    if response.status_code not in (200, 201):
        raise _error_from(response)
    return response.json()


def get_data(callback_code: str) -> dict:
    response = _call("GET", "/api/v1/sdk/data", params={"code": callback_code})
    if response.status_code != 200:
        raise _error_from(response)
    return response.json()


def get_session(session_id: str) -> dict:
    response = _call("GET", f"/api/v1/sdk/sessions/{session_id}")
    if response.status_code != 200:
        raise _error_from(response)
    return response.json()


def parse_expires_at(value) -> datetime:
    parsed = parse_datetime(str(value or "")) if value else None
    if parsed is None:
        parsed = timezone.now() + timedelta(minutes=10)
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


# ── tekshiruv natijasini ishlash ────────────────────────────────────────────

def mark_failed(session_id: str, reason: str, status="failed") -> None:
    """Faqat kutilayotgan sessiyani yakunlaydi (takroriy webhook allaqachon yakunlanganini buzmaydi)."""
    from .models import FaceIDSession

    FaceIDSession.objects.filter(session_id=session_id, status__in=["pending", "processing"]).update(
        status=status, failure_reason=(reason or "")[:50], finished_at=timezone.now()
    )


def finish_session(record_id: int, callback_code: str) -> None:
    """
    session.passed: callback_code bilan natijani olish, shaxsni tekshirish va hujjatni tasdiqlash.
    Takroriy chaqiruvdan himoya: pending → processing o'tishi faqat bitta chaqiruvda muvaffaqiyatli bo'ladi.
    """
    from .deed_signing import SigningError, approve_as_signer
    from .models import FaceIDSession

    if not FaceIDSession.objects.filter(pk=record_id, status="pending").update(status="processing"):
        return
    record = FaceIDSession.objects.select_related("employee", "deed").get(pk=record_id)

    try:
        data = get_data(callback_code)
    except FaceIDError as e:
        mark_failed(record.session_id, e.code)
        return

    verification = data.get("verification") or {}
    identity = data.get("identity") or {}
    if (
        data.get("session_id") != record.session_id
        or verification.get("status") != "passed"
        or not record.employee.pinfl
        or str(identity.get("pinfl") or "") != record.employee.pinfl
    ):
        logger.warning("FaceID natijasi mos kelmadi (session=%s)", record.session_id)
        mark_failed(record.session_id, "PINFL_MISMATCH")
        return

    try:
        approve_as_signer(record.deed_id, record.employee, record.role, record.message)
    except SigningError as e:
        mark_failed(record.session_id, e.code)
        return

    FaceIDSession.objects.filter(pk=record.pk).update(
        status="approved",
        similarity=verification.get("similarity"),
        liveness_score=verification.get("liveness_score"),
        finished_at=timezone.now(),
    )


def refresh_from_faceid(record) -> None:
    """Webhook kelmay qolsa zaxira: FaceID'dan sessiya holatini so'rab, natijani qo'llaydi (3 soniyada bir martadan ko'p emas)."""
    if record.status != "pending" or not cache.add(f"faceid_poll_{record.pk}", 1, 3):
        return
    try:
        info = get_session(record.session_id)
    except FaceIDError:
        return
    state = info.get("status")
    if state == "passed" and info.get("callback_code"):
        finish_session(record.pk, info["callback_code"])
    elif state in ("failed", "cancelled", "expired"):
        mark_failed(record.session_id, {"failed": "FACE_MISMATCH", "cancelled": "SESSION_CANCELLED"}.get(state, "SESSION_EXPIRED"),
                    status="expired" if state == "expired" else "failed")


def expire_if_overdue(record) -> None:
    if record.status == "pending" and record.expires_at <= timezone.now():
        mark_failed(record.session_id, "SESSION_EXPIRED", status="expired")
