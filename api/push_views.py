"""
Brauzer push (Web Push, VAPID) obunasi — yangi interfeys (React) uchun:

  GET  /api/v1/push/public-key/                          — {"public_key": "..."} (brauzer obunasi uchun VAPID kaliti)
  POST /api/v1/push/subscribe/    {endpoint, keys: {p256dh, auth}}  — shu qurilma obunasini xodimga bog'lash
  POST /api/v1/push/unsubscribe/  {endpoint}                         — obunani o'chirish
  GET  /api/v1/push/status/?endpoint=...                             — shu qurilma obuna bo'lganmi ({"subscribed": bool})

Yuborish: main.push_views.send_push_notification → Celery (main.tasks.send_push_notification_task).
"""
from urllib.parse import urlparse

from django.conf import settings
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import PushSubscription


def _employee(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")
    return employee


# Obuna manzili (endpoint) faqat ma'lum brauzer push xizmatlariniki bo'la oladi. Aks holda foydalanuvchi serverga
# ixtiyoriy manzilga so'rov yuborishni (SSRF) buyura olardi: yuborish vazifasi endpoint'ga POST qiladi.
PUSH_HOSTS = (
    "fcm.googleapis.com",                 # Chrome, Edge, Opera, Samsung (FCM)
    "android.googleapis.com",
    ".push.services.mozilla.com",         # Firefox
    ".notify.windows.com",                # Edge/Windows (WNS)
    ".push.apple.com",                    # Safari
)


def _allowed_push_host(host):
    hosts = tuple(getattr(settings, "PUSH_ENDPOINT_HOSTS", PUSH_HOSTS))
    return any(host == h.lstrip(".") or (h.startswith(".") and host.endswith(h)) for h in hosts)


def _endpoint(raw):
    endpoint = (raw or "").strip()
    parsed = urlparse(endpoint)
    # Faqat HTTPS (maydon uzunligi — modelda 1000), standart port, login/parolsiz va ruxsat etilgan push xizmati
    if (
        parsed.scheme != "https" or not parsed.hostname or len(endpoint) > 1000
        or parsed.username or parsed.password or parsed.port not in (None, 443)
        or not _allowed_push_host(parsed.hostname.lower())
    ):
        raise ValidationError({"endpoint": "Noto'g'ri obuna manzili"})
    return endpoint


class PushPublicKeyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        key = getattr(settings, "VAPID_PUBLIC_KEY", "")
        if not key:
            raise ValidationError({"detail": "Brauzer push sozlanmagan"})
        return Response({"public_key": key})


class PushSubscribeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        employee = _employee(request)
        endpoint = _endpoint(request.data.get("endpoint"))
        keys = request.data.get("keys") or {}
        if not isinstance(keys, dict):
            raise ValidationError({"keys": "Noto'g'ri format"})
        p256dh = str(keys.get("p256dh") or "").strip()
        auth = str(keys.get("auth") or "").strip()
        if not p256dh or not auth or len(p256dh) > 200 or len(auth) > 200:
            raise ValidationError({"keys": "Obuna ma'lumotlari to'liq emas"})

        # Bir xil qurilma qayta obuna bo'lsa dublikat yaratilmaydi; boshqa xodim kirgan bo'lsa qayta bog'lanadi
        _, created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "employee": employee,
                "p256dh": p256dh,
                "auth": auth,
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300],
            },
        )
        return Response({"subscribed": True}, status=201 if created else 200)


class PushUnsubscribeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        employee = _employee(request)
        endpoint = _endpoint(request.data.get("endpoint"))
        PushSubscription.objects.filter(employee=employee, endpoint=endpoint).delete()
        return Response({"subscribed": False})


class PushStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        employee = _employee(request)
        endpoint = (request.query_params.get("endpoint") or "").strip()
        subscribed = bool(endpoint) and PushSubscription.objects.filter(employee=employee, endpoint=endpoint).exists()
        return Response({"subscribed": subscribed})
