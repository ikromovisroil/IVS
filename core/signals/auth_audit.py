# core/signals/auth_audit.py
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from core.models import AuditLog


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    try:
        AuditLog.objects.create(
            employee=getattr(user, "employee", None),
            action="login",
            model="User",
            object_id=user.id,
            path=request.path if request else "",
            method="LOGIN",
            ip=request.META.get("REMOTE_ADDR") if request else None,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300] if request else "",
            description="Login",
        )
    except Exception:
        pass


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if not user:
        return
    try:
        AuditLog.objects.create(
            employee=getattr(user, "employee", None),
            action="logout",
            model="User",
            object_id=user.id,
            path=request.path if request else "",
            method="LOGOUT",
            ip=request.META.get("REMOTE_ADDR") if request else None,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300] if request else "",
            description="Logout",
        )
    except Exception:
        pass