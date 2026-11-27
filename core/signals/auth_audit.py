# core/signals/auth_audit.py
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from core.models import AuditLog
from core.request_context import get_client_ip


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    # Mobil kirishning brauzer bosqichi yozilmaydi: ilova JWT olganda yoziladi (api/auth_views.py)
    if getattr(request, "mobile_login_flow", False):
        return
    record_login(request, user)


def record_login(request, user, description="Login"):
    """Kirishni audit jurnaliga yozadi (qurilma turi va versiya so'rovdan olinadi)."""
    try:
        AuditLog.objects.create(
            employee=getattr(user, "employee", None),
            action="login",
            model="User",
            object_id=user.id,
            path=request.path if request else "",
            method="LOGIN",
            ip=get_client_ip(request) if request else None,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300] if request else "",
            description=description,
        )
    except Exception:
        pass


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if not user or getattr(request, "mobile_login_flow", False):
        return
    try:
        AuditLog.objects.create(
            employee=getattr(user, "employee", None),
            action="logout",
            model="User",
            object_id=user.id,
            path=request.path if request else "",
            method="LOGOUT",
            ip=get_client_ip(request) if request else None,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300] if request else "",
            description="Logout",
        )
    except Exception:
        pass
