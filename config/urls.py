from django.conf import settings
from django.conf.urls.static import static
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

# JWT Token Views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from django.contrib import admin
from django.urls import path, include
schema_view = get_schema_view(
    openapi.Info(
        title="IMV API Documentation",
        default_version='v1',
        description="IMV API Hujjatlari",
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # ADMIN PANEL
    path('admin/', admin.site.urls),

    # MAIN SITE
    path("", include("main.urls")),
    path("sso/", include("users.urls")),

    # API
    path('api/', include('main.api_urls')),

    # JWT TOKEN URL'lari
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # SWAGGER
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='swagger'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='redoc'),
]

# STATIC & MEDIA
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    from django.views.static import serve
    from django.urls import re_path

    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]
