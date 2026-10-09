"""Uchrashuvlar (Zoom) — sayt sahifasi. Android uchun API: api/meeting_views.py."""
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required

from . import zoom
from .meetings import MeetingError, can_open, cancel_meeting, create_meeting, finish_meeting, meetings_for
from .models import Meeting


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


@never_cache
@require_GET
@login_required
def meetings_page(request):
    employee = _employee(request)
    if not can_open(request.user):
        raise PermissionDenied("Uchrashuvlarni ko'rish huquqi yo'q")
    now = timezone.now()
    items = list(meetings_for(employee))
    for m in items:
        m.is_mine = m.organizer_id == employee.id
        m.is_running = m.start_at <= now
    upcoming = [m for m in items if m.status == Meeting.STATUS_SCHEDULED and m.start_at + timedelta(minutes=m.duration_minutes) >= now]
    past = [m for m in reversed(items) if m not in upcoming][:30]
    return render(request, "chat/meetings.html", {
        "upcoming": upcoming,
        "past": past,
        "zoom_enabled": zoom.zoom_enabled(),
    })


@never_cache
@require_POST
@login_required
def meeting_create(request):
    employee = _employee(request)
    try:
        create_meeting(
            employee,
            title=request.POST.get("title"),
            start_at=parse_local_datetime(request.POST.get("start_at")),
            duration_minutes=request.POST.get("duration") or 30,
            agenda=request.POST.get("agenda") or "",
        )
    except MeetingError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Uchrashuv yaratildi")
    return redirect("meetings_page")


@never_cache
@require_POST
@login_required
def meeting_finish(request, pk):
    employee = _employee(request)
    meeting = get_object_or_404(Meeting, pk=pk)
    try:
        finish_meeting(meeting, employee)
    except MeetingError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Uchrashuv tugatildi, vaqt bo'shadi")
    return redirect("meetings_page")


@never_cache
@require_POST
@login_required
def meeting_cancel(request, pk):
    employee = _employee(request)
    meeting = get_object_or_404(Meeting, pk=pk)
    try:
        cancel_meeting(meeting, employee)
    except MeetingError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Uchrashuv bekor qilindi")
    return redirect("meetings_page")
