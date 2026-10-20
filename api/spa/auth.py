"""
Kirish sahifasi uchun (tizimga kirishdan oldin ochiladi):

* config/ — SSO sozlanganmi (.env: SSO_AUTH_URL, SSO_CLIENT_ID) va login/parol bilan kirish ochiqmi
  (.env: SSO_REQUIRED=0). Shu so'rov csrftoken cookie'sini ham o'rnatadi.
* login/  — login/parol bilan sessiyaga kirish; faqat SSO_REQUIRED=0 bo'lganda.
"""
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.urls import path
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.auth_views import LoginThrottle


def _sso_configured() -> bool:
    return bool(settings.SSO_AUTH_URL and settings.SSO_CLIENT_ID)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class AuthConfigView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({
            "sso_enabled": _sso_configured(),
            "password_login": not settings.SSO_REQUIRED,
        })


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


@method_decorator(csrf_protect, name="dispatch")  # sessiyasiz so'rov ham CSRF tekshiriladi (login CSRF)
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        if settings.SSO_REQUIRED:
            return Response({"detail": "Kirish faqat SSO orqali."}, status=status.HTTP_403_FORBIDDEN)

        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = authenticate(request._request, **ser.validated_data)
        if user is None:
            return Response({"detail": "Login yoki parol noto'g'ri."}, status=status.HTTP_400_BAD_REQUEST)

        login(request._request, user)
        return Response({"username": user.username})


urlpatterns = [
    path("config/", AuthConfigView.as_view()),
    path("login/", LoginView.as_view()),
]
