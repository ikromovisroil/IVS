from django.conf import settings
from django.conf.urls.static import static
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from main.views import error_403, error_404, error_500

handler403 = error_403
handler404 = error_404
handler500 = error_500

# JWT Token Views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from django.contrib import admin
from django.urls import path, include, re_path

API_DESCRIPTION = """
**IMV API (Android uchun)** — to'liq qo'llanma: `docs/ANDROID_API.md`.

### Kirish (SSO)
Ikki variant: **A** — SSO hujjatidagi standart oqim: `POST /api/auth/sso/token/ {code, code_verifier, redirect_uri}` (ilovaning redirect_uri si SSO'da ro'yxatdan o'tgan bo'lishi kerak); **B** — quyidagi brauzer orqali oqim (qo'shimcha ro'yxatdan o'tkazish kerak emas).
1. Ilova tasodifiy `code_verifier` (43–128 belgi) yaratadi, `code_challenge = BASE64URL(SHA256(code_verifier))` (paddingsiz, 43 belgi).
2. Brauzer (Custom Tab) da `GET /api/auth/mobile/start/?code_challenge=...` ochiladi → SSO sahifasi.
3. Muvaffaqiyatli kirgach brauzer ilovaga qaytadi: `ivsapp://auth?code=...` (kod 2 daqiqa amal qiladi).
4. `POST /api/auth/mobile/exchange/` `{code, code_verifier}` → `{access, refresh, employee}`.
5. So'rovlar: `Authorization: Bearer <access>`; access 1 soat. Yangilash: `POST /api/token/refresh/` `{refresh}` — **har safar yangi refresh qaytadi, eskisi bekor bo'ladi, yangisini saqlang**.
6. Chiqish: `POST /api/auth/logout/` `{refresh}`.
Tizimda yo'q foydalanuvchiga 403: "Siz tizimda ro'yxatda yo'qsiz".

### Foydalanuvchi turi va imkoniyatlar
Kirgandan keyin `GET /api/me/`: `organization_type` (`worker` — ATM vakili, `client` — mijoz), `orders.can_*` bayroqlari va `permissions`.
Ekranlarni shu bayroqlarga qarab ko'rsating; ruxsatsiz amalni server baribir **403** bilan rad etadi.

### Versiyalash
Asosiy manzil `/api/v1/` (eski `/api/` ham ishlaydi). Ilova ochilganda `GET /api/v1/app/config/?version=...` — majburiy yangilash va texnik ishlar holati; so'rovlarga `X-App-Version` sarlavhasini qo'shing (eski versiyaga 426).

### Umumiy qoidalar
Ro'yxatlar 20 tadan sahifalanadi: `?page=`, `?page_size=` (100 gacha); javob `count/next/previous/results`.
Xatolar: `400` — tekshiruv xatosi (`{"maydon": ["..."]}` yoki `{"detail": "..."}`), `401` — token yo'q/eskirgan, `403` — ruxsat yo'q, `404` — topilmadi yoki ko'rinmaydi.
Fayllar (rasm, PDF) — `multipart/form-data`.
"""

# Swagger faqat tizimga kirgan foydalanuvchiga (SWAGGER_PUBLIC=1 bo'lsa hamma uchun ochiq)
schema_view = get_schema_view(
    openapi.Info(
        title="IMV API Documentation",
        default_version="v1",
        description=API_DESCRIPTION,
    ),
    public=True,
    permission_classes=[permissions.AllowAny if getattr(settings, "SWAGGER_PUBLIC", False) else permissions.IsAuthenticated],
    patterns=[path('api/v1/', include('api.urls'))],
)

urlpatterns = [
    # ADMIN PANEL
    path('ivc_service_admin_panel/', admin.site.urls),

    # MAIN SITE
    path("", include("main.urls")),

    # CHAT
    path("chat/", include("chat.urls")),

    # API
    path('api/v1/', include('api.urls')),   # asosiy (versiyalangan) manzil

    # JWT TOKEN URL'lari

    # SWAGGER
    re_path(r"^swagger(?P<format>\.json|\.yaml)$", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]

# STATIC & MEDIA
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    from django.views.static import serve

    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]