"""Bildirishnomalar markazi (sayt): ro'yxat, ochish (o'qilgan qiladi), hammasini o'qilgan qilish, hisoblagich."""
from django.core.exceptions import PermissionDenied

from .models import Notification

KINDS = {kind for kind, _ in Notification.KINDS}


def _employee(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")
    return employee


