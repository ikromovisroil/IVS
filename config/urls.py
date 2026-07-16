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

schema_view = get_schema_view(
    openapi.Info(
        title="IMV API Documentation",
        default_version="v1",
        description="IMV API Hujjatlari",
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # ADMIN PANEL
    path('ivc_service_admin_panel/', admin.site.urls),

    # MAIN SITE
    path("", include("main.urls")),

    # API
    path('api/', include('api.urls')),

    # JWT TOKEN URL'lari
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

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