"""
Zoom uchrashuvlari (Android). Sayt bilan bir xil servis (chat/meetings.py).

  GET  /api/v1/meetings/?scope=upcoming|past|all   — men yaratgan uchrashuvlar
  POST /api/v1/meetings/                           — yaratish {title, start_at, duration_minutes, agenda?}
  GET  /api/v1/meetings/{id}/                      — bitta uchrashuv
  POST /api/v1/meetings/{id}/cancel/               — bekor qilish (faqat tashkilotchi)
"""
from datetime import timedelta

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from chat.meeting_views import parse_local_datetime
from chat.meetings import MeetingError, can_open, cancel_meeting, create_meeting, finish_meeting, meetings_for
from chat.models import Meeting


def _employee(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")
    if not can_open(request.user):
        raise PermissionDenied("Uchrashuvlarga ruxsat yo'q")
    return employee


def meeting_json(meeting, me):
    mine = meeting.organizer_id == me.id
    data = {
        "id": meeting.id,
        "title": meeting.title,
        "agenda": meeting.agenda,
        "start_at": meeting.start_at.isoformat(),
        "duration_minutes": meeting.duration_minutes,
        "status": meeting.status,
        "ended_at": meeting.ended_at.isoformat() if meeting.ended_at else None,
        "organizer": {"id": meeting.organizer_id, "name": meeting.organizer.full_name},
        "join_url": meeting.join_url,
        "password": meeting.password,
        "invitation": meeting.invitation,
        "is_organizer": mine,
        "can_manage": mine,   # boshlash/tugatish/nusxalash/o'chirish faqat yaratgan xodimda
    }
    if mine:
        data["start_url"] = meeting.start_url   # faqat tashkilotchiga
    return data


class MeetingListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(manual_parameters=[
        openapi.Parameter("scope", openapi.IN_QUERY, description="upcoming (standart) | past | all", type=openapi.TYPE_STRING),
    ])
    def get(self, request):
        me = _employee(request)
        scope = (request.query_params.get("scope") or "upcoming").strip()
        if scope not in ("upcoming", "past", "all"):
            raise ValidationError({"scope": "upcoming, past yoki all"})
        now = timezone.now()
        items = list(meetings_for(me))
        def is_upcoming(m):
            return m.status == Meeting.STATUS_SCHEDULED and m.start_at + timedelta(minutes=m.duration_minutes) >= now
        if scope == "upcoming":
            items = [m for m in items if is_upcoming(m)]
        elif scope == "past":
            items = [m for m in reversed(items) if not is_upcoming(m)]
        return Response({"results": [meeting_json(m, me) for m in items]})

    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT, required=["title", "start_at"],
        properties={
            "title": openapi.Schema(type=openapi.TYPE_STRING),
            "start_at": openapi.Schema(type=openapi.TYPE_STRING, description="ISO sana-vaqt, masalan 2026-10-15T15:00:00+05:00"),
            "duration_minutes": openapi.Schema(type=openapi.TYPE_INTEGER, description="15–480, standart 30"),
            "agenda": openapi.Schema(type=openapi.TYPE_STRING),
        },
    ))
    def post(self, request):
        me = _employee(request)
        data = request.data
        try:
            meeting = create_meeting(
                me,
                title=data.get("title"),
                start_at=parse_local_datetime(str(data.get("start_at") or "")),
                duration_minutes=data.get("duration_minutes") or 30,
                agenda=data.get("agenda") or "",
            )
        except MeetingError as exc:
            if not request.user.has_perm("chat.add_meeting"):
                raise PermissionDenied(str(exc))
            raise ValidationError({"detail": str(exc)})
        return Response(meeting_json(meeting, me), status=201)


class MeetingDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        me = _employee(request)
        meeting = meetings_for(me).filter(pk=pk).first()
        if not meeting:
            raise NotFound("Uchrashuv topilmadi")
        return Response(meeting_json(meeting, me))


class MeetingCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        me = _employee(request)
        meeting = get_object_or_404(Meeting, pk=pk)
        if not meetings_for(me).filter(pk=pk).exists():
            raise NotFound("Uchrashuv topilmadi")
        try:
            cancel_meeting(meeting, me)
        except MeetingError as exc:
            raise PermissionDenied(str(exc))
        return Response(meeting_json(meeting, me))


class MeetingFinishView(APIView):
    """POST /api/v1/meetings/{id}/finish/ — boshlangan uchrashuvni rejadan oldin tugatish (faqat tashkilotchi); vaqt bo'shaydi."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        me = _employee(request)
        meeting = get_object_or_404(Meeting, pk=pk)
        if not meetings_for(me).filter(pk=pk).exists():
            raise NotFound("Uchrashuv topilmadi")
        try:
            finish_meeting(meeting, me)
        except MeetingError as exc:
            raise ValidationError({"detail": str(exc)})
        return Response(meeting_json(meeting, me))
