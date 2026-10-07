"""
/api/ so'rovlari uchun qo'riqchi:
 * javobga `X-API-Version` sarlavhasi qo'shadi;
 * texnik ishlar (API_MAINTENANCE=1) paytida 503 qaytaradi;
 * ilova `X-App-Version: 1.0.3` yuborsa va u ANDROID_MIN_VERSION dan eski bo'lsa — 426 (majburiy yangilash).
Sarlavha yuborilmasa (brauzer, Swagger) cheklov qo'llanmaydi. `app/config/` har doim ochiq.
"""
from django.conf import settings
from django.http import JsonResponse

from .app_views import API_VERSION, app_status, maintenance_info


def _is_api(path):
    return path.startswith("/api/")


def _is_config(path):
    return path.rstrip("/").endswith("/api/app/config") or path.rstrip("/").endswith("/api/v1/app/config")


class ApiGuardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not _is_api(path):
            return self.get_response(request)

        if not _is_config(path):
            maint = maintenance_info()
            if maint["enabled"]:
                resp = JsonResponse({"code": "maintenance", "detail": maint["message"]}, status=503)
                resp["Retry-After"] = "300"
                resp["X-API-Version"] = "1"
                return resp

            version = (request.headers.get("X-App-Version") or "").strip()
            if version:
                force, _ = app_status(version)
                if force:
                    resp = JsonResponse({
                        "code": "upgrade_required",
                        "detail": getattr(settings, "ANDROID_UPDATE_MESSAGE", "")
                                  or "Ilovaning yangi versiyasi chiqdi. Davom etish uchun yangilang.",
                        "min_version": getattr(settings, "ANDROID_MIN_VERSION", ""),
                        "update_url": getattr(settings, "ANDROID_UPDATE_URL", ""),
                    }, status=426)
                    resp["X-API-Version"] = "1"
                    return resp

        response = self.get_response(request)
        response["X-API-Version"] = "1"
        return response
