"""
Bildirishnomalar markazi (Android):

  GET  /api/v1/notifications/?kind=order|deed|meeting|chat|system&unread=1  — ro'yxat (sahifalangan)
  GET  /api/v1/notifications/unread-count/                                 — {"unread": N}
  POST /api/v1/notifications/{id}/read/                                    — bittasini o'qilgan qilish
  POST /api/v1/notifications/read-all/  {"kind"?: "order"}                 — hammasini (yoki turini) o'qilgan qilish
"""
from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Notification
from core.notifications import mark_all_read, mark_read, unread_count

from .pagination import StandardResultsPagination

KINDS = {kind for kind, _ in Notification.KINDS}


def _employee(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")
    return employee


def notification_json(n):
    return {
        "id": n.id,
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "url": n.url,
        "count": n.count,
        "is_read": n.is_read,
        "date_creat": n.date_creat.isoformat(),
    }


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(manual_parameters=[
        openapi.Parameter("kind", openapi.IN_QUERY, description="order | deed | meeting | chat | system", type=openapi.TYPE_STRING),
        openapi.Parameter("unread", openapi.IN_QUERY, description="1 bo'lsa faqat o'qilmaganlar", type=openapi.TYPE_STRING),
    ])
    def get(self, request):
        employee = _employee(request)
        qs = Notification.objects.filter(employee=employee)
        kind = (request.query_params.get("kind") or "").strip()
        if kind in KINDS:
            qs = qs.filter(kind=kind)
        if (request.query_params.get("unread") or "").strip() in ("1", "true", "True"):
            qs = qs.filter(is_read=False)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        response = paginator.get_paginated_response([notification_json(n) for n in page])
        response.data["unread"] = unread_count(employee)
        return response


class NotificationUnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"unread": unread_count(_employee(request))})


class NotificationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        employee = _employee(request)
        notification = get_object_or_404(Notification, pk=pk, employee=employee)
        mark_read(employee, [notification.id])
        notification.refresh_from_db()
        return Response(notification_json(notification))


class NotificationReadAllView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={"kind": openapi.Schema(type=openapi.TYPE_STRING, description="ixtiyoriy: faqat shu turni")},
    ))
    def post(self, request):
        employee = _employee(request)
        kind = str(request.data.get("kind") or "").strip()
        updated = mark_all_read(employee, kind=kind if kind in KINDS else None)
        return Response({"updated": updated, "unread": unread_count(employee)})
