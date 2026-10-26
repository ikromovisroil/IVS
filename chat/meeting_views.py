"""Uchrashuvlar (Zoom) — sayt sahifasi. Android uchun API: api/meeting_views.py."""

from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.utils.dateparse import parse_datetime



def _employee(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")
    return employee


def parse_local_datetime(raw):
    """'2026-10-15T15:00' (datetime-local) yoki ISO sana-vaqt -> aware datetime (mahalliy vaqt zonasida)."""
    dt = parse_datetime((raw or "").strip())
    if dt is None:
        return None
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


