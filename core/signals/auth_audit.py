from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from core.models import AuditLog

@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    AuditLog.objects.create(
        employee=getattr(user, "employee", None),
        action="login",
        model="User",
        object_id=user.id,
        path=request.path,
        method="LOGIN",
        ip=request.META.get("REMOTE_ADDR"),
        description="Login",
    )

@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    AuditLog.objects.create(
        employee=getattr(user, "employee", None),
        action="logout",
        model="User",
        object_id=user.id,
        description="Logout",
    )
