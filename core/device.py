"""
So'rov qaysi qurilmadan kelganini aniqlash. Mobil ilova barcha so'rovlarga `X-Device-Type: ios|android` va
`X-App-Version: 1.0.3` sarlavhalarini qo'shadi; brauzer hech narsa yubormaydi va cookie'si bo'yicha `web` deb olinadi.
Aniqlab bo'lmasa (sarlavhasiz eski ilova, tashqi xizmat) — bo'sh satr.

Qiymat so'rov davomida `current_device()` orqali olinadi: ariza, hujjat va audit yozuvi yaratilganda model o'zi o'qiydi.
"""
from contextvars import ContextVar

from django.conf import settings

DEVICE_CHOICES = [("web", "Web"), ("ios", "iOS"), ("android", "Android")]
_VALID = {value for value, _ in DEVICE_CHOICES}
_current: ContextVar[tuple[str, str]] = ContextVar("ivs_device", default=("", ""))


def detect_device(request) -> tuple[str, str]:
    """(device_type, app_version)."""
    device = (request.headers.get("X-Device-Type") or "").strip().lower()
    version = (request.headers.get("X-App-Version") or "").strip()[:30]
    if device not in _VALID:
        browser = settings.SESSION_COOKIE_NAME in request.COOKIES or settings.CSRF_COOKIE_NAME in request.COOKIES
        bearer = (request.headers.get("Authorization") or "").startswith("Bearer ")
        device = "web" if browser and not bearer else ""
    return device, version


def current_device() -> tuple[str, str]:
    """Joriy so'rovning (device_type, app_version); so'rovdan tashqarida (Celery, buyruqlar) — ('', '')."""
    return _current.get()


def set_current_device(value: tuple[str, str]):
    return _current.set(value)


def reset_current_device(token) -> None:
    _current.reset(token)
