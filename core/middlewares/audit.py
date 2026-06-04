# core/middlewares/audit.py
from core.models import AuditLog

SKIP_PATHS = ("/static/", "/media/", "/favicon", "/admin/jsi18n/")


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Faqat login bo'lgan userlar
        if not request.user.is_authenticated:
            return response

        # Keraksiz pathlarni o'tkazib yuborish
        if any(request.path.startswith(p) for p in SKIP_PATHS):
            return response

        # Faqat o'zgartiruvchi metodlar
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return response

        try:
            AuditLog.objects.create(
                employee=getattr(request.user, "employee", None),
                action=self._get_action(request.method),
                model="HTTP",
                object_id=None,
                path=request.path,
                method=request.method,
                ip=self._get_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
                description=f"{request.method} {request.path}",
            )
        except Exception:
            pass  # log yozilmasa ham asosiy jarayon to'xtamasin

        return response

    def _get_ip(self, request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    def _get_action(self, method):
        return {
            "POST":   "create",
            "PUT":    "update",
            "PATCH":  "update",
            "DELETE": "delete",
        }.get(method, "update")