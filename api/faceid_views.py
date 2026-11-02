"""
FaceID bilan hujjatni tasdiqlash (veb va Android):

* GET  faceid/config/            — FaceID yoqilganmi: {"enabled": bool}
* POST faceid/sessions/          — {"deed_id", "message"?}: sessiya yaratadi, ilova SDK uchun session_id/sdk_token/nonce/challenges qaytaradi
* GET  faceid/sessions/<id>/     — sessiya holati (pending | processing | approved | failed | expired); webhook kelmasa zaxira so'rov
* POST faceid/webhook/           — FaceID natijasi (imzo bilan himoyalangan, tizimga kirish talab qilinmaydi)

Natijaga faqat server ishonadi: hujjat webhook va FaceID'dan olingan ma'lumot (PINFL mosligi) bo'yicha tasdiqlanadi.
"""
import json
import logging
import uuid

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from main import faceid
from main.models import Deed, FaceIDSession
from main.tasks import process_faceid_result

from .permissions import DeedConsentPermission

logger = logging.getLogger(__name__)


class FaceIDSessionThrottle(UserRateThrottle):
    scope = "faceid"

    def get_rate(self):
        return "10/min"


def _employee(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")
    return employee


def _require_enabled():
    if not faceid.enabled():
        return Response({"detail": "FaceID hozircha yoqilmagan"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return None


class FaceIDConfigView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"enabled": faceid.enabled()})


class SessionCreateSerializer(serializers.Serializer):
    deed_id = serializers.IntegerField()
    message = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class FaceIDSessionCreateView(APIView):
    permission_classes = [DeedConsentPermission]
    throttle_classes = [FaceIDSessionThrottle]

    def post(self, request):
        disabled = _require_enabled()
        if disabled:
            return disabled
        employee = _employee(request)
        ser = SessionCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        deed = get_object_or_404(Deed, pk=ser.validated_data["deed_id"])

        # E-IMZO bilan bir xil tekshiruvlar (api/spa/messages.py:ApproveStartView)
        if deed.receiver_id == employee.id:
            role, current = "receiver", deed.status_receiver
        elif deed.sender_id == employee.id:
            role, current = "sender", deed.status_sender
        else:
            raise PermissionDenied("Sizga ruxsat yo'q")
        if current != "viewed":
            raise ValidationError({"detail": "Bu hujjat holatida amal bajarib bo'lmaydi"})

        from main.views import validate_pdf_file

        ok, error = validate_pdf_file(deed.file)
        if not ok:
            raise ValidationError({"detail": error})

        pinfl = (employee.pinfl or "").strip()
        if len(pinfl) != 14 or not pinfl.isdigit() or not employee.birth_date:
            raise ValidationError({"detail": "Profilingizda PINFL yoki tug'ilgan sana yo'q. SSO orqali qayta kiring."})

        try:
            info = faceid.create_session(
                pinfl, employee.birth_date, idempotency_key=str(uuid.uuid4()),
                metadata={"deed_id": deed.id, "employee_id": employee.id},
            )
        except faceid.FaceIDError as e:
            http = e.http_status if e.http_status in (400, 404, 429) else 502
            message = faceid.failure_message(e.code) if e.code == "IDENTITY_NOT_FOUND" else (
                "FaceID xizmati vaqtincha ishlamayapti. Birozdan keyin urinib ko'ring." if http == 502 else str(e))
            return Response({"detail": message, "code": e.code}, status=http)

        record = FaceIDSession.objects.create(
            employee=employee, deed=deed, role=role, message=ser.validated_data["message"].strip(),
            session_id=info["session_id"], expires_at=faceid.parse_expires_at(info.get("expires_at")),
        )
        return Response({
            "id": record.id,
            "session_id": info["session_id"],
            "sdk_token": info.get("sdk_token"),
            "nonce": info.get("nonce"),
            "challenges": info.get("challenges") or [],
            "expires_at": info.get("expires_at"),
        }, status=status.HTTP_201_CREATED)


class FaceIDSessionDetailView(APIView):
    permission_classes = [DeedConsentPermission]

    def get(self, request, pk):
        employee = _employee(request)
        record = get_object_or_404(FaceIDSession.objects.select_related("deed"), pk=pk, employee=employee)
        faceid.expire_if_overdue(record)
        if faceid.enabled():
            faceid.refresh_from_faceid(record)
        record.refresh_from_db()
        deed = record.deed
        reason = record.failure_reason
        return Response({
            "id": record.id,
            "status": record.status,
            "deed_id": record.deed_id,
            "role": record.role,
            "failure_reason": reason or None,
            "message": faceid.failure_message(reason) if record.status in ("failed", "expired") else None,
            "retry": record.status in ("failed", "expired") and reason not in faceid.NO_RETRY,
            "expires_at": record.expires_at,
            "deed": {"status_sender": deed.status_sender, "status_receiver": deed.status_receiver},
        })


def _dispatch(record_id, callback_code):
    """Natijani fonda ishlash (webhook tez javob berishi uchun). Broker ishlamasa shu so'rovning o'zida bajariladi."""
    try:
        process_faceid_result.delay(record_id, callback_code)
    except Exception:
        logger.exception("FaceID natijasini navbatga qo'yib bo'lmadi, to'g'ridan-to'g'ri bajariladi")
        faceid.finish_session(record_id, callback_code)


class FaceIDWebhookView(APIView):
    authentication_classes = []        # sessiyasiz: CSRF tekshirilmaydi, ishonch imzo orqali
    permission_classes = [permissions.AllowAny]
    throttle_classes = []

    def post(self, request):
        if not faceid.enabled():
            return Response({"detail": "FaceID yoqilmagan"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        raw = request.body   # imzo xom baytlar ustida tekshiriladi
        timestamp = request.headers.get("X-FaceID-Timestamp", "")
        signature = request.headers.get("X-FaceID-Signature", "")
        if not faceid.timestamp_is_fresh(timestamp) or not faceid.verify_signature(
            settings.FACEID_WEBHOOK_SECRET, timestamp, raw, signature
        ):
            return Response({"detail": "Imzo yaroqsiz"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            payload = json.loads(raw or b"{}")
        except ValueError:
            return Response({"detail": "JSON noto'g'ri"}, status=status.HTTP_400_BAD_REQUEST)

        event = payload.get("event")
        session_id = str(payload.get("session_id") or "")
        record = FaceIDSession.objects.filter(session_id=session_id).first()
        if record is None or record.status != "pending":
            return Response({"ok": True})      # noma'lum yoki allaqachon ishlangan (takroriy yetkazish)

        if event == "session.passed" and payload.get("callback_code"):
            code = str(payload["callback_code"])
            _dispatch(record.id, code)
        elif event == "session.failed":
            faceid.mark_failed(session_id, str(payload.get("failure_reason") or "FAILED"))
        return Response({"ok": True})
