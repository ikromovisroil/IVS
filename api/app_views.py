"""
Ilova konfiguratsiyasi va majburiy yangilash (Android).

GET /api/v1/app/config/?platform=android&version=1.0.3 — autentifikatsiyasiz (ilova ochilganda, kirishdan oldin).
Sozlamalar (.env): ANDROID_MIN_VERSION (shundan eski versiya ishlay olmaydi), ANDROID_LATEST_VERSION,
ANDROID_UPDATE_URL, ANDROID_UPDATE_MESSAGE; API_MAINTENANCE=1 va API_MAINTENANCE_MESSAGE (texnik ishlar).
"""
import re

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

API_VERSION = "v1"


def parse_version(value):
    """'1.2.3' -> (1, 2, 3); noto'g'ri qiymat -> None."""
    if not value or not isinstance(value, str):
        return None
    parts = []
    for chunk in value.strip().split("."):
        m = re.match(r"\d+", chunk)
        if not m:
            return None
        parts.append(int(m.group()))
    return tuple(parts) if parts else None


def _cmp(a, b):
    """a < b ? (uzunligi har xil bo'lsa nol bilan to'ldiriladi)."""
    n = max(len(a), len(b))
    pa, pb = a + (0,) * (n - len(a)), b + (0,) * (n - len(b))
    return (pa > pb) - (pa < pb)


def app_status(version_str):
    """Ilova versiyasi holati: (force_update, update_available)."""
    current = parse_version(version_str)
    minimum = parse_version(getattr(settings, "ANDROID_MIN_VERSION", ""))
    latest = parse_version(getattr(settings, "ANDROID_LATEST_VERSION", ""))
    force = bool(current and minimum and _cmp(current, minimum) < 0)
    available = bool(current and latest and _cmp(current, latest) < 0)
    return force or False, available or force


def maintenance_info():
    return {
        "enabled": bool(getattr(settings, "API_MAINTENANCE", False)),
        "message": getattr(settings, "API_MAINTENANCE_MESSAGE", "") or "Texnik ishlar olib borilmoqda. Birozdan keyin urinib ko'ring.",
    }


class AppConfigView(APIView):
    """Ilova versiyasini tekshirish: majburiy yangilash, yangilanish mavjudligi, texnik ishlar holati."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        platform = (request.query_params.get("platform") or "android").lower()
        version = (request.query_params.get("version") or "").strip()
        force, available = app_status(version)
        return Response({
            "api_version": API_VERSION,
            "server_time": timezone.now().isoformat(),
            "app": {
                "platform": platform,
                "current_version": version or None,
                "latest_version": getattr(settings, "ANDROID_LATEST_VERSION", "") or None,
                "min_version": getattr(settings, "ANDROID_MIN_VERSION", "") or None,
                "update_available": available,
                "force_update": force,
                "update_url": getattr(settings, "ANDROID_UPDATE_URL", "") or None,
                "message": getattr(settings, "ANDROID_UPDATE_MESSAGE", "") or (
                    "Ilovaning yangi versiyasi chiqdi. Davom etish uchun yangilang." if force else ""
                ),
            },
            "maintenance": maintenance_info(),
        })
