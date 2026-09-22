# core/middlewares/audit.py
from core.models import AuditLog
from core.request_context import (
    set_current_employee, was_signal_logged, get_client_ip, clear,
)

SKIP_PATHS = (
    "/static/", "/media/", "/favicon",
    "/ivc_service_admin_panel/jsi18n/",
    "/ajax/push-subscribe/",
)


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        employee = getattr(request.user, "employee", None) if request.user.is_authenticated else None
        set_current_employee(employee)

        try:
            response = self.get_response(request)

            if not request.user.is_authenticated:
                return response

            if any(request.path.startswith(p) for p in SKIP_PATHS):
                return response

            if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
                return response

            # Shu so'rov davomida biror model-signal (masalan Order/Deed)
            # allaqachon aniqroq (model + object_id bilan) yozuv qoldirgan
            # bo'lsa, umumiy HTTP yozuvini qo'shib, dublikat hosil qilmaymiz.
            if was_signal_logged():
                return response

            try:
                AuditLog.objects.create(
                    employee=employee,
                    action=self._get_action(request.method),
                    model="HTTP",
                    object_id=None,
                    path=request.path,
                    method=request.method,
                    ip=get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
                    description=f"{request.method} {request.path}",
                )
            except Exception:
                pass  # log yozilmasa ham asosiy jarayon to'xtamasin

            return response
        finally:
            clear()

    def _get_action(self, method):
        return {
            "POST":   "create",
            "PUT":    "update",
            "PATCH":  "update",
            "DELETE": "delete",
        }.get(method, "update")
