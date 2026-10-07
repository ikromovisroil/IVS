"""
Android (mobil) ilova uchun SSO orqali kirish.

Oqim (veb-saytdagi SSO'ga tegmaydi, SSO provayderida yangi redirect_uri ham kerak emas):

1. Ilova PKCE juftligini yaratadi: code_verifier (tasodifiy) va code_challenge = BASE64URL(SHA256(verifier)).
2. Ilova brauzerni (Custom Tab) ochadi:  GET /api/auth/mobile/start/?code_challenge=...
   Server challenge'ni sessiyada saqlab, odatdagi veb SSO login'ga yo'naltiradi.
3. Foydalanuvchi SSO'dan o'tgach, sso_exchange uni /api/auth/mobile/complete/ ga yo'naltiradi.
4. Server qisqa muddatli imzolangan "code" yaratib, ilovaning deep link'iga qaytaradi:
   <MOBILE_APP_REDIRECT>?code=...
5. Ilova POST /api/auth/mobile/exchange/ {code, code_verifier} yuboradi va JWT (access/refresh) oladi.
   Code faqat code_verifier egasi uchun ishlaydi (deep link tutib olingan taqdirda ham foydasiz).
6. Keyingi so'rovlar: Authorization: Bearer <access>; yangilash: POST /api/token/refresh/.
"""
import base64
import hashlib
import hmac
import re

from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.core import signing
from django.http import HttpResponse
from django.utils.html import escape
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import EmployeeSerializer

CODE_SALT = "ivs-mobile-login"
CODE_MAX_AGE = 120  # soniya
_CHALLENGE_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")  # SHA-256 BASE64URL (paddingsiz)


def mobile_app_redirect():
    return getattr(settings, "MOBILE_APP_REDIRECT", "ivsapp://auth")


def _challenge_of(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii", "ignore")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@never_cache
def mobile_login_start(request):
    """Ilova brauzerda shu manzilni ochadi."""
    challenge = (request.GET.get("code_challenge") or "").strip()
    if not _CHALLENGE_RE.match(challenge):
        return Response_bad("code_challenge noto'g'ri (BASE64URL(SHA256), 43 belgi)")

    request.session["MOBILE_LOGIN"] = {"challenge": challenge}
    request.session["SSO_FLOW"] = {"purpose": "login"}
    request.session.modified = True
    return redirect("sso_start")


def Response_bad(message):
    from django.http import JsonResponse
    return JsonResponse({"detail": message}, status=400)


@never_cache
def mobile_login_complete(request):
    """sso_exchange muvaffaqiyatli bo'lgach brauzer shu yerga keladi — ilovaga qaytaramiz."""
    pending = request.session.get("MOBILE_LOGIN")
    if not request.user.is_authenticated or not pending:
        return Response_bad("Mobil kirish sessiyasi topilmadi. Qaytadan urinib ko'ring.")

    code = signing.dumps(
        {"uid": request.user.pk, "ch": pending["challenge"]},
        salt=CODE_SALT,
    )
    # Brauzer sessiyasi ilovaga kerak emas — yopamiz (JWT beriladi).
    auth_logout(request)
    app_url = escape(f"{mobile_app_redirect()}?code={code}")
    # Maxsus sxema (ivsapp://) ga Django redirect qilmaydi; sahifa avtomatik ochadi, tugma zaxira uchun.
    html = (
        '<!doctype html><html lang="uz"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>IVS</title></head><body style="font-family:sans-serif;text-align:center;padding:48px 16px">'
        '<p>Ilovaga qaytilmoqda...</p>'
        f'<p><a href="{app_url}" style="font-size:18px">Ilovani ochish</a></p>'
        f'<script>window.location.replace("{app_url}");</script>'
        '</body></html>'
    )
    return HttpResponse(html)


def _token_response(user):
    refresh = RefreshToken.for_user(user)
    employee = getattr(user, "employee", None)
    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "employee": EmployeeSerializer(employee).data if employee else None,
    })


class LoginThrottle(AnonRateThrottle):
    """Login/parol bilan kirish (faqat admin hisoblari) — brute-force dan himoya."""
    rate = "30/min"


class MobileExchangeThrottle(AnonRateThrottle):
    rate = "20/min"


class MobileLoginExchangeView(APIView):
    """POST /api/auth/mobile/exchange/ {code, code_verifier} -> {access, refresh, employee}"""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [MobileExchangeThrottle]

    def post(self, request):
        code = (request.data.get("code") or "").strip()
        verifier = (request.data.get("code_verifier") or "").strip()
        if not code or not (43 <= len(verifier) <= 128):
            return Response({"detail": "code yoki code_verifier noto'g'ri"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = signing.loads(code, salt=CODE_SALT, max_age=CODE_MAX_AGE)
        except signing.BadSignature:
            return Response({"detail": "Kod yaroqsiz yoki muddati o'tgan"}, status=status.HTTP_400_BAD_REQUEST)

        if not hmac.compare_digest(_challenge_of(verifier), str(data.get("ch", ""))):
            return Response({"detail": "code_verifier mos kelmadi"}, status=status.HTTP_400_BAD_REQUEST)

        from django.contrib.auth import get_user_model
        user = get_user_model().objects.filter(pk=data.get("uid"), is_active=True).first()
        if not user:
            return Response({"detail": "Foydalanuvchi topilmadi yoki bloklangan"}, status=status.HTTP_403_FORBIDDEN)

        return _token_response(user)


class LogoutView(APIView):
    """POST /api/auth/logout/ {refresh, fcm_token?} — refresh tokenni bekor qiladi (va shu qurilmaning push tokenini o'chiradi)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Qurilma tokenini ham olib tashlash (chiqqandan keyin bildirishnoma kelmasligi uchun)
        fcm_token = str(request.data.get("fcm_token") or "").strip()
        if fcm_token:
            from core.models import MobileDevice
            MobileDevice.objects.filter(token=fcm_token, employee__user=request.user).delete()
        try:
            RefreshToken(request.data.get("refresh", "")).blacklist()
        except TokenError:
            return Response({"detail": "Token yaroqsiz"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SsoCodeLoginView(APIView):
    """
    POST /api/auth/sso/token/ {code, code_verifier, redirect_uri} -> {access, refresh, employee}

    SSO hujjatidagi standart oqim: ilova foydalanuvchini SSO sahifasiga (sso.mf.uz/oauth2/login) o'zi yo'naltiradi
    (clientId, redirectUri, codeChallenge bilan), SSO ilovaning `redirect_uri` iga `code` qaytaradi, ilova `code`
    va `code_verifier` ni shu endpointga yuboradi. Server `client-secret` bilan SSO'dan token oladi
    (client-secret ilovada bo'lmaydi) va o'zining JWT'ini beradi.

    Shart: ilovaning `redirect_uri` si SSO clientida ro'yxatdan o'tgan bo'lishi va serverda
    MOBILE_SSO_REDIRECT_URIS (vergul bilan) ro'yxatiga kiritilgan bo'lishi kerak; aks holda endpoint o'chiq (503).
    Faqat tizimda mavjud xodimlar kira oladi (Gateway ishlatilmaydi).
    """

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [MobileExchangeThrottle]

    def post(self, request):
        from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
        from main.models import Employee
        from main.sso_utils import decode_jwt
        from main.sso_views import exchange_code_for_token

        allowed = getattr(settings, "MOBILE_SSO_REDIRECT_URIS", [])
        if not allowed:
            return Response({"detail": "Bu kirish usuli hozircha yoqilmagan"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        code = (request.data.get("code") or "").strip()
        verifier = (request.data.get("code_verifier") or "").strip()
        redirect_uri = (request.data.get("redirect_uri") or "").strip()
        if not code or not (43 <= len(verifier) <= 128) or not redirect_uri:
            return Response({"detail": "code, code_verifier yoki redirect_uri noto'g'ri"}, status=status.HTTP_400_BAD_REQUEST)
        if redirect_uri not in allowed:
            return Response({"detail": "redirect_uri ruxsat etilmagan"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token_data = exchange_code_for_token(code, verifier, redirect_uri) or {}
        except DjangoPermissionDenied:
            return Response({"detail": "SSO kodi qabul qilinmadi yoki muddati o'tgan"}, status=status.HTTP_400_BAD_REQUEST)

        pinfl = str((decode_jwt(token_data.get("id_token") or "") or {}).get("pinfl") or "").strip()
        if not pinfl:
            return Response({"detail": "SSO javobida PINFL topilmadi"}, status=status.HTTP_403_FORBIDDEN)

        employee = Employee.objects.select_related("user").filter(pinfl=pinfl).first()
        if not employee or not employee.user:
            return Response({"detail": "Siz tizimda ro'yxatda yo'qsiz"}, status=status.HTTP_403_FORBIDDEN)
        if not employee.user.is_active:
            return Response({"detail": "Foydalanuvchi bloklangan"}, status=status.HTTP_403_FORBIDDEN)

        return _token_response(employee.user)


class DeviceRegisterView(APIView):
    """
    POST /api/devices/ {"token": "<FCM token>", "device_name": "...", "app_version": "..."}  -> {"id", "created"}

    Android ilova kirgandan keyin (va FCM token yangilanganda — onNewToken) chaqiradi.
    Token yagona: boshqa xodimga biriktirilgan bo'lsa (qurilma qo'ldan-qo'lga o'tgan) joriy xodimga ko'chiriladi.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from core.models import MobileDevice

        employee = getattr(request.user, "employee", None)
        if not employee:
            return Response({"detail": "Employee yo'q"}, status=status.HTTP_403_FORBIDDEN)

        token = str(request.data.get("token") or "").strip()
        if not (20 <= len(token) <= 1024):
            return Response({"detail": "token noto'g'ri"}, status=status.HTTP_400_BAD_REQUEST)

        device, created = MobileDevice.objects.update_or_create(
            token=token,
            defaults={
                "employee": employee,
                "platform": "android",
                "device_name": str(request.data.get("device_name") or "")[:100],
                "app_version": str(request.data.get("app_version") or "")[:30],
                "is_active": True,
            },
        )
        return Response({"id": device.id, "created": created},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class DeviceUnregisterView(APIView):
    """POST /api/devices/unregister/ {"token": "..."} — shu qurilmaga bildirishnoma yuborishni to'xtatish (204)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from core.models import MobileDevice

        token = str(request.data.get("token") or "").strip()
        if token:
            MobileDevice.objects.filter(token=token, employee__user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
