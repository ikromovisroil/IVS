"""
Chat va Zoom bo'limi (React: frontend/src/pages/comms/) — /api/v1/spa/comms/.

Chat va uchrashuvlarning o'zi mavjud API orqali ishlaydi (/api/v1/chat/..., /api/v1/meetings/...; real vaqt —
WebSocket /ws/chat/). Bu yerda faqat eski sahifadagi, API'da yo'q ma'lumot:

  GET meetings/config/  — {"zoom_enabled": bool, "hosts": [{"id": 1, "name": "Zoom 1"}, ...]}: Zoom sozlanmagan bo'lsa ogohlantirish chiqadi va
                          "Yaratish" tugmasi o'chiriladi (templates/chat/meetings.html dagi kabi).
"""
from django.urls import path
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from chat import zoom
from chat.meetings import can_open


class MeetingsConfig(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not getattr(request.user, "employee", None):
            raise PermissionDenied("Employee yo'q")
        if not can_open(request.user):
            raise PermissionDenied("Uchrashuvlarni ko'rish huquqi yo'q")
        hosts = [{"id": i, "name": f"Zoom {i}"} for i in range(1, len(zoom.zoom_hosts()) + 1)]
        return Response({"zoom_enabled": zoom.zoom_enabled(), "hosts": hosts})


urlpatterns = [
    path("meetings/config/", MeetingsConfig.as_view(), name="spa_comms_meetings_config"),
]
